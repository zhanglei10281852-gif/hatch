from __future__ import annotations

import os
from collections import deque
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from hatch.cli.application import Application
    from hatch.project.core import Project
    from hatch.utils.platform import Platform


class ChangedSinceError(Exception):
    """Raised when the projects affected by a `--changed-since` revision cannot be determined."""


@click.command(short_help="Build a project")
@click.argument("location", required=False)
@click.option(
    "--target",
    "-t",
    "targets",
    multiple=True,
    help=(
        "The target to build, overriding project defaults. This may be selected multiple times e.g. `-t sdist -t wheel`"
    ),
)
@click.option(
    "--all",
    "-a",
    "build_all",
    is_flag=True,
    help=(
        "Whether or not to build the workspace root and every workspace member defined by the selected "
        "environment. Artifacts are written to the workspace root's `dist` directory by default"
    ),
)
@click.option(
    "--changed-since",
    metavar="REF",
    default=None,
    help=(
        "With `--all`, only build projects whose tracked files changed relative to the given Git reference, along "
        "with every project that directly or transitively depends on them. Untracked files are ignored, the merge "
        "base is not used and every project must be located in the same Git working tree"
    ),
)
@click.option(
    "--hooks-only", is_flag=True, help="Whether or not to only execute build hooks [env var: `HATCH_BUILD_HOOKS_ONLY`]"
)
@click.option(
    "--no-hooks", is_flag=True, help="Whether or not to disable build hooks [env var: `HATCH_BUILD_NO_HOOKS`]"
)
@click.option(
    "--ext",
    is_flag=True,
    help=(
        "Whether or not to only execute build hooks for distributing binary Python packages, such as "
        "compiling extensions. Equivalent to `--hooks-only -t wheel`"
    ),
)
@click.option(
    "--clean",
    "-c",
    is_flag=True,
    help="Whether or not existing artifacts should first be removed [env var: `HATCH_BUILD_CLEAN`]",
)
@click.option(
    "--clean-hooks-after",
    is_flag=True,
    help=(
        "Whether or not build hook artifacts should be removed after each build "
        "[env var: `HATCH_BUILD_CLEAN_HOOKS_AFTER`]"
    ),
)
@click.option("--clean-only", is_flag=True, hidden=True)
@click.pass_obj
def build(
    app: Application,
    location,
    targets,
    build_all,
    changed_since,
    hooks_only,
    no_hooks,
    ext,
    clean,
    clean_hooks_after,
    clean_only,
):
    """Build a project."""
    app.ensure_environment_plugin_dependencies()

    from hatch.config.constants import AppEnvVars
    from hatch.project.constants import DEFAULT_BUILD_DIRECTORY
    from hatch.utils.fs import Path

    if ext:
        hooks_only = True
        targets = ("wheel",)
    elif not targets:
        targets = ("sdist", "wheel")

    env_vars = {}
    if app.verbose:
        env_vars[AppEnvVars.VERBOSE] = str(app.verbosity)
    elif app.quiet:
        env_vars[AppEnvVars.QUIET] = str(abs(app.verbosity))

    if not build_all:
        if changed_since is not None:
            app.abort("The `--changed-since` option can only be used together with the `--all` flag")

        _build_project(
            app,
            app.project,
            location,
            targets,
            hooks_only=hooks_only,
            no_hooks=no_hooks,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
            env_vars=env_vars,
        )
        return

    environment = app.project.get_environment()
    members = environment.workspace.members
    if not members:
        app.abort(
            f"The `--all` flag requires workspace members to be defined in field "
            f"`tool.hatch.envs.{environment.name}.workspace.members`"
        )

    # The workspace root is built without needing to be listed as a member, but only when it
    # defines a project itself rather than merely being a container for workspace configuration
    projects = [app.project] if app.project.defines_project else []
    projects.extend(member.project for member in members if member.project.location != app.project.location)

    if changed_since is not None:
        # The complete set of projects must be determined before any build environment preparation,
        # artifact generation or cleanup begins
        try:
            changed_projects = select_changed_projects(app.platform, projects, changed_since)
        except ChangedSinceError as e:
            app.abort(str(e))

        if not changed_projects:
            app.display_info(f"No tracked file changes detected since `{changed_since}`, nothing to build")
            return

        projects = changed_projects

    # Artifacts from every project are consolidated in a single directory, defaulting to the
    # workspace root. The location must be absolute because each member builds from its own path
    build_directory = str(Path(location).resolve() if location else app.project.location / DEFAULT_BUILD_DIRECTORY)

    for project in projects:
        if not clean_only:
            app.display_header(project.metadata.name)

        _build_project(
            app,
            project,
            build_directory,
            targets,
            hooks_only=hooks_only,
            no_hooks=no_hooks,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
            env_vars=env_vars,
        )


def select_changed_projects(platform: Platform, projects: list[Project], ref: str) -> list[Project]:
    """Select the projects that must be built for `hatch build --all --changed-since REF`.

    The selection is derived solely from tracked file changes between the given Git reference and
    the current working tree, combined with the reverse dependency relationships between candidate
    projects. No package index is queried and no artifacts are produced or removed.
    """
    # Every candidate project must be in the same Git working tree so that a single diff
    # against the reference is meaningful for all of them
    worktree_root = _get_common_worktree_root(platform, projects)
    _verify_git_reference(platform, worktree_root, ref)

    changed_paths = _get_changed_paths(platform, worktree_root, ref)
    if not changed_paths:
        return []

    affected_projects = _attribute_changed_paths(changed_paths, worktree_root, projects)

    # A tracked change outside of every candidate project cannot be attributed safely, so
    # conservatively build every candidate
    if affected_projects is None:
        return list(projects)

    # Build a map of PEP 503 normalized package names so that dependency relationships can be
    # established regardless of the original spelling of the names
    from hatch.utils.metadata import normalize_project_name

    normalized_names: dict[str, Project] = {}
    for project in projects:
        name = normalize_project_name(project.metadata.name)
        existing = normalized_names.get(name)
        if existing is not None:
            message = (
                f"The package names of `{existing.metadata.name}` (`{existing.location}`) and "
                f"`{project.metadata.name}` (`{project.location}`) normalize to the same name `{name}`, "
                f"so the affected projects cannot be determined unambiguously"
            )
            raise ChangedSinceError(message)

        normalized_names[name] = project

    # Map each project to the normalized names of its runtime dependencies and of every optional
    # dependency group. Version constraints, environment markers and whether an optional group is
    # enabled deliberately do not narrow this conservative relationship
    dependents: dict[int, set[Project]] = {id(project): set() for project in projects}
    for project in projects:
        for dependency_name in _get_project_dependency_names(project):
            dependency = normalized_names.get(dependency_name)
            if dependency is not None and dependency is not project:
                dependents[id(dependency)].add(project)

    # Follow the reverse dependency edges from the directly affected projects. A visited set keeps
    # the traversal finite in the presence of dependency cycles and ensures each project is built
    # at most once
    selected_ids: set[int] = set()
    queue = deque(affected_projects)
    while queue:
        project = queue.popleft()
        if id(project) in selected_ids:
            continue

        selected_ids.add(id(project))
        queue.extend(dependents[id(project)])

    # Preserve the candidate ordering used by the regular `build --all` command
    return [project for project in projects if id(project) in selected_ids]


def _get_common_worktree_root(platform: Platform, projects: list[Project]) -> str:
    roots: set[str] = set()
    for project in projects:
        process = _run_git(platform, project.location, "rev-parse", "--show-toplevel")
        if process.returncode:
            stderr = process.stderr.decode("utf-8", errors="replace").strip()
            detail = stderr or "not a Git repository"
            message = (
                f"Project `{project.metadata.name}` at `{project.location}` is not located within a Git "
                f"working tree: {detail}"
            )
            raise ChangedSinceError(message)

        roots.add(_normalize_path(process.stdout.decode("utf-8", errors="replace").strip()))

    if len(roots) > 1:
        formatted_roots = ", ".join(sorted(roots))
        message = (
            "The `--changed-since` option requires every workspace project to be located in the same Git "
            f"working tree, found multiple working trees: {formatted_roots}"
        )
        raise ChangedSinceError(message)

    return next(iter(roots))


def _verify_git_reference(platform: Platform, worktree_root: str, ref: str) -> None:
    # The `^{commit}` suffix ensures the reference can be peeled to an actual commit rather than,
    # for example, merely existing as an ambiguous object name
    process = _run_git(platform, worktree_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if process.returncode:
        message = f"Invalid Git reference `{ref}` passed to `--changed-since`"
        raise ChangedSinceError(message)


def _get_changed_paths(platform: Platform, worktree_root: str, ref: str) -> list[str]:
    # Compare the reference directly with the current working tree (no merge base). This includes
    # committed changes since the reference as well as staged and unstaged modifications of tracked
    # files, while untracked files are never reported. Renames are disabled so that a rename is
    # emitted as the deletion of the old path and the addition of the new path, allowing both sides
    # of a cross-member rename to be attributed. The NUL separator keeps paths with spaces or other
    # special characters intact and unquoted.
    process = _run_git(platform, worktree_root, "diff", "--name-only", "--no-renames", "-z", ref)
    if process.returncode:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        message = f"Unable to determine the changes since `{ref}`: {stderr or 'the Git command failed'}"
        raise ChangedSinceError(message)

    output = process.stdout.decode("utf-8", errors="replace")
    return [path for path in output.split("\0") if path]


def _attribute_changed_paths(
    changed_paths: list[str], worktree_root: str, projects: list[Project]
) -> set[Project] | None:
    normalized_projects = [(project, _normalize_path(project.location)) for project in projects]

    affected: set[Project] = set()
    for relative_path in changed_paths:
        changed_path = _normalize_path(os.path.join(worktree_root, relative_path))

        owner: Project | None = None
        owner_path: str | None = None
        for project, project_path in normalized_projects:
            if not _is_within(changed_path, project_path):
                continue

            # Attribute to the deepest containing project directory so that similarly named
            # directories cannot shadow each other
            if owner_path is None or len(project_path) > len(owner_path):
                owner = project
                owner_path = project_path

        if owner is None:
            return None

        affected.add(owner)

    return affected


def _get_project_dependency_names(project: Project) -> set[str]:
    from hatch.dep.core import Dependency, InvalidDependencyError
    from hatch.utils.metadata import normalize_project_name

    try:
        dependencies, optional_dependencies = project.get_dependencies()
    except Exception as e:
        message = (
            f"Unable to resolve the dependency metadata of project `{project.metadata.name}` at "
            f"`{project.location}`: {e}"
        )
        raise ChangedSinceError(message) from e

    requirement_strings = list(dependencies)
    for feature_dependencies in optional_dependencies.values():
        requirement_strings.extend(feature_dependencies)

    names: set[str] = set()
    for requirement_string in requirement_strings:
        try:
            requirement = Dependency(requirement_string)
        except InvalidDependencyError as e:
            message = (
                f"Unable to parse dependency `{requirement_string}` of project `{project.metadata.name}` "
                f"at `{project.location}`: {e}"
            )
            raise ChangedSinceError(message) from e

        names.add(normalize_project_name(requirement.name))

    return names


def _is_within(path: str, directory: str) -> bool:
    return path == directory or path.startswith(directory + os.sep)


def _normalize_path(path: str | os.PathLike) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


def _run_git(platform: Platform, cwd: str | os.PathLike, *args: str):
    command = ["git", "-C", os.fspath(cwd), *args]
    try:
        return platform.run_command(command, capture_output=True)
    except FileNotFoundError as e:
        message = "The `--changed-since` option requires Git to be installed and available on PATH"
        raise ChangedSinceError(message) from e


def _build_project(
    app: Application,
    project: Project,
    location,
    targets,
    *,
    hooks_only,
    no_hooks,
    clean,
    clean_hooks_after,
    clean_only,
    env_vars,
):
    from hatch.project.config import env_var_enabled
    from hatch.project.constants import BUILD_BACKEND, DEFAULT_BUILD_DIRECTORY, BuildEnvVars
    from hatch.utils.fs import Path
    from hatch.utils.runner import ExecutionContext
    from hatch.utils.structures import EnvVars

    build_dir = Path(location).resolve() if location else None

    with EnvVars(env_vars):
        project.prepare_build_environment(targets=[target.split(":")[0] for target in targets])

    build_backend = project.metadata.build.build_backend
    with project.location.as_cwd(), project.build_env.get_env_vars():
        for target in targets:
            target_name, _, _ = target.partition(":")
            if not clean_only:
                app.display_header(target_name)

            if build_backend != BUILD_BACKEND:
                if target_name == "sdist":
                    directory = build_dir or project.location / DEFAULT_BUILD_DIRECTORY
                    directory.ensure_dir_exists()
                    artifact_path = project.build_frontend.build_sdist(directory)
                elif target_name == "wheel":
                    directory = build_dir or project.location / DEFAULT_BUILD_DIRECTORY
                    directory.ensure_dir_exists()
                    artifact_path = project.build_frontend.build_wheel(directory)
                else:
                    app.abort(f"Target `{target_name}` is not supported by `{build_backend}`")

                app.display_info(
                    str(artifact_path.relative_to(project.location))
                    if project.location in artifact_path.parents
                    else str(artifact_path)
                )
            else:
                command = ["python", "-u", "-m", "hatchling", "build", "--target", target]

                # We deliberately pass the location unchanged so that absolute paths may be non-local
                # and reflect wherever builds actually take place
                if location:
                    command.extend(("--directory", str(location)))

                if hooks_only or env_var_enabled(BuildEnvVars.HOOKS_ONLY):
                    command.append("--hooks-only")

                if no_hooks or env_var_enabled(BuildEnvVars.NO_HOOKS):
                    command.append("--no-hooks")

                if clean or env_var_enabled(BuildEnvVars.CLEAN):
                    command.append("--clean")

                if clean_hooks_after or env_var_enabled(BuildEnvVars.CLEAN_HOOKS_AFTER):
                    command.append("--clean-hooks-after")

                if clean_only:
                    command.append("--clean-only")

                context = ExecutionContext(project.build_env)
                context.add_shell_command(command)
                context.env_vars.update(env_vars)
                app.execute_context(context)
