from __future__ import annotations

import subprocess

import pytest

from hatch.cli.build import ChangedSinceError, select_changed_projects
from hatch.utils.fs import Path

REF = "abc1234"


class FakeMetadata:
    def __init__(self, name):
        self.name = name


class FakeProject:
    def __init__(self, location, name, dependencies=(), optional_dependencies=None, failure=None):
        self.location = Path(location)
        self.metadata = FakeMetadata(name)
        self._dependencies = list(dependencies)
        self._optional_dependencies = optional_dependencies or {}
        self._failure = failure
        self.dependency_calls = 0

    def get_dependencies(self):
        self.dependency_calls += 1
        if self._failure is not None:
            raise self._failure

        optional = {group: list(deps) for group, deps in self._optional_dependencies.items()}
        return list(self._dependencies), optional


class FakeProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeGitPlatform:
    def __init__(
        self,
        root,
        *,
        toplevels=None,
        toplevel_failures=(),
        ref_valid=True,
        diff_stdout=b"",
        diff_returncode=0,
        diff_stderr=b"",
        missing=False,
    ):
        self.root = str(root)
        self.toplevels = toplevels or {}
        self.toplevel_failures = {str(path) for path in toplevel_failures}
        self.ref_valid = ref_valid
        self.diff_stdout = diff_stdout
        self.diff_returncode = diff_returncode
        self.diff_stderr = diff_stderr
        self.missing = missing
        self.commands = []

    def run_command(self, command, **kwargs):
        self.commands.append((list(command), kwargs))
        if self.missing:
            message = "git"
            raise FileNotFoundError(message)

        # ["git", "-C", <cwd>, *args]
        cwd = str(command[2])
        args = command[3:]

        if args[0] == "rev-parse" and "--show-toplevel" in args:
            if cwd in self.toplevel_failures:
                return FakeProcess(128, stderr=b"fatal: not a git repository (or any of the parent directories)")

            toplevel = self.toplevels.get(cwd, self.root)
            return FakeProcess(stdout=toplevel.encode() + b"\n")

        if args[0] == "rev-parse" and "--verify" in args:
            return FakeProcess(0 if self.ref_valid else 1, stdout=b"abc1234\n" if self.ref_valid else b"")

        if args[0] == "diff":
            return FakeProcess(self.diff_returncode, stdout=self.diff_stdout, stderr=self.diff_stderr)

        message = f"Unexpected git command: {command}"
        raise AssertionError(message)


def _names(projects):
    return [project.metadata.name for project in projects]


class TestSelectChangedProjects:
    @pytest.fixture
    def workspace(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root, "workspace-root"),
            FakeProject(root / "packages" / "foo", "foo"),
            FakeProject(root / "packages" / "foobar", "foobar"),
            FakeProject(root / "packages" / "bar", "bar"),
        ]
        return root, projects

    def test_no_changes_returns_empty_without_resolving_dependencies(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root)

        assert select_changed_projects(platform, projects, REF) == []
        assert all(project.dependency_calls == 0 for project in projects)

    def test_invalid_reference(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, ref_valid=False)

        with pytest.raises(ChangedSinceError, match=rf"Invalid Git reference `{REF}`"):
            select_changed_projects(platform, projects, REF)

    def test_reference_verification_uses_commit_peel_suffix(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root)

        select_changed_projects(platform, projects, REF)

        verify_commands = [command for command, _ in platform.commands if "--verify" in command]
        assert verify_commands
        assert f"{REF}^{{commit}}" in verify_commands[0]

    def test_missing_git_executable(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, missing=True)

        with pytest.raises(ChangedSinceError, match="requires Git to be installed"):
            select_changed_projects(platform, projects, REF)

    def test_project_outside_git_worktree(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, toplevel_failures=[projects[1].location])

        with pytest.raises(ChangedSinceError, match="not located within a Git working tree"):
            select_changed_projects(platform, projects, REF)

    def test_projects_in_different_worktrees(self, workspace):
        root, projects = workspace
        other_root = str(root.parent / "other-worktree")
        platform = FakeGitPlatform(
            root,
            toplevels={
                str(projects[0].location): str(root),
                str(projects[1].location): str(root),
                str(projects[2].location): other_root,
                str(projects[3].location): other_root,
            },
        )

        with pytest.raises(ChangedSinceError, match="same Git working tree"):
            select_changed_projects(platform, projects, REF)

    def test_diff_command_failure(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_returncode=128, diff_stderr=b"fatal: bad revision")

        with pytest.raises(ChangedSinceError, match="Unable to determine the changes since"):
            select_changed_projects(platform, projects, REF)

    def test_diff_command_disables_renames_and_uses_nul_separator(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_stdout=b"packages/foo/__init__.py\x00")

        select_changed_projects(platform, projects, REF)

        diff_commands = [command for command, _ in platform.commands if command and command[3] == "diff"]
        assert diff_commands
        diff_command = diff_commands[0]
        assert "--no-renames" in diff_command
        assert "-z" in diff_command
        # The reference is compared directly, without computing a merge base
        assert diff_command[-1] == REF
        assert "..." not in diff_command

    def test_attribution_to_deepest_member(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_stdout=b"packages/foo/pkg/nested/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["foo"]

    def test_similar_directory_names_do_not_shadow_each_other(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_stdout=b"packages/foobar/pkg/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["foobar"]

    def test_paths_with_spaces(self, workspace):
        root, projects = workspace
        spaced_project = FakeProject(root / "packages" / "my package", "my-package")
        projects.append(spaced_project)
        platform = FakeGitPlatform(
            root,
            diff_stdout=b"packages/my package/src/my package/module.py\x00",
        )

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["my-package"]

    def test_deleted_file_attributes_to_original_member(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_stdout=b"packages/bar/removed_module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["bar"]

    def test_cross_member_rename_affects_both_members(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(
            root,
            diff_stdout=b"packages/foo/moved.py\x00packages/bar/moved.py\x00",
        )

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["foo", "bar"]

    def test_orphan_change_conservatively_selects_every_candidate(self, temp_dir):
        root = temp_dir / "virtual-root"
        # The root only contains workspace configuration, so it is not itself a candidate
        projects = [
            FakeProject(root / "packages" / "foo", "foo"),
            FakeProject(root / "packages" / "bar", "bar"),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"unrelated/top-level-file.txt\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert selected == projects

    def test_root_level_change_attributes_to_root_project(self, workspace):
        root, projects = workspace
        platform = FakeGitPlatform(root, diff_stdout=b"pyproject.toml\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["workspace-root"]

    def test_reverse_dependencies_are_added_transitively(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "a", "a"),
            FakeProject(root / "b", "b", dependencies=['a==1.0; python_version >= "3.8"']),
            FakeProject(root / "c", "c", dependencies=["b>=2.0"]),
            FakeProject(root / "d", "d", dependencies=["some-external-package"]),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"a/src/a/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        # Constraints and markers do not remove the relationship, the unrelated project is excluded
        assert _names(selected) == ["a", "b", "c"]

    def test_all_optional_dependency_groups_are_considered(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "a", "a"),
            FakeProject(
                root / "b",
                "b",
                optional_dependencies={"dev": ["a"], "docs": ["sphinx"]},
            ),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"a/src/a/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["a", "b"]

    def test_dependency_cycles_terminate_and_select_each_project_once(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "a", "a", dependencies=["b"]),
            FakeProject(root / "b", "b", dependencies=["a"]),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"b/src/b/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["a", "b"]

    def test_ambiguous_normalized_package_names(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "a", "foo.bar"),
            FakeProject(root / "b", "foo-bar"),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"a/src/module.py\x00")

        with pytest.raises(ChangedSinceError, match="normalize to the same name `foo-bar`"):
            select_changed_projects(platform, projects, REF)

    def test_dependency_metadata_resolution_failure(self, temp_dir):
        root = temp_dir / "workspace"
        failure = RuntimeError("dynamic metadata backend exploded")
        projects = [
            FakeProject(root / "a", "a"),
            FakeProject(root / "b", "b", failure=failure),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"a/src/module.py\x00")

        with pytest.raises(ChangedSinceError, match="Unable to resolve the dependency metadata of project `b`"):
            select_changed_projects(platform, projects, REF)

    def test_invalid_dependency_string(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "a", "a"),
            FakeProject(root / "b", "b", dependencies=["!!!not-a-requirement"]),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"a/src/module.py\x00")

        with pytest.raises(ChangedSinceError, match="Unable to parse dependency"):
            select_changed_projects(platform, projects, REF)

    def test_selection_preserves_candidate_order(self, temp_dir):
        root = temp_dir / "workspace"
        projects = [
            FakeProject(root / "root", "root-project"),
            FakeProject(root / "a", "a", dependencies=["b"]),
            FakeProject(root / "b", "b", dependencies=["c"]),
            FakeProject(root / "c", "c"),
        ]
        platform = FakeGitPlatform(root, diff_stdout=b"c/src/c/module.py\x00")

        selected = select_changed_projects(platform, projects, REF)
        assert _names(selected) == ["a", "b", "c"]

    def test_untracked_changes_are_not_reported_by_git(self, workspace):
        root, projects = workspace
        # The Git invocation only surfaces tracked paths, so an empty diff means nothing is selected
        platform = FakeGitPlatform(root, diff_stdout=b"")

        assert select_changed_projects(platform, projects, REF) == []
        diff_commands = [command for command, _ in platform.commands if command and command[3] == "diff"]
        assert diff_commands


def _run_git(cwd, *args):
    process = subprocess.run(["git", *args], check=False, cwd=str(cwd), capture_output=True, text=True)
    assert process.returncode == 0, process.stderr


@pytest.mark.requires_git
class TestChangedSinceWithRealGit:
    def test_tracked_change_states_untracked_files_and_renames(self, temp_dir):
        from hatch.utils.platform import Platform

        repo = temp_dir / "repo"
        alpha_dir = repo / "packages" / "alpha"
        beta_dir = repo / "packages" / "beta"
        docs_dir = repo / "docs"
        for directory in (alpha_dir, beta_dir, docs_dir):
            directory.mkdir(parents=True)

        (alpha_dir / "module.py").write_text("value = 1\n")
        (beta_dir / "module.py").write_text("value = 1\n")
        (docs_dir / "readme.md").write_text("documentation\n")

        _run_git(repo, "init")
        _run_git(repo, "config", "--local", "user.name", "test")
        _run_git(repo, "config", "--local", "user.email", "test@example.com")
        _run_git(repo, "add", "-A")
        _run_git(repo, "commit", "-m", "baseline")

        projects = [
            FakeProject(alpha_dir, "alpha"),
            FakeProject(beta_dir, "beta", dependencies=["alpha"]),
        ]
        platform = Platform()

        # No tracked changes
        assert select_changed_projects(platform, projects, "HEAD") == []

        # An untracked file must not influence the selection
        (alpha_dir / "untracked.py").write_text("value = 2\n")
        assert select_changed_projects(platform, projects, "HEAD") == []

        # Unstaged modification of a tracked file
        (alpha_dir / "module.py").write_text("value = 2\n")
        selected = select_changed_projects(platform, projects, "HEAD")
        assert _names(selected) == ["alpha", "beta"]

        # Staged modification of a tracked file
        _run_git(repo, "checkout", "HEAD", "--", ".")
        (beta_dir / "module.py").write_text("value = 2\n")
        _run_git(repo, "add", "packages/beta/module.py")
        selected = select_changed_projects(platform, projects, "HEAD")
        assert _names(selected) == ["beta"]

        # A tracked change outside every member conservatively selects every candidate
        (docs_dir / "readme.md").write_text("updated documentation\n")
        selected = select_changed_projects(platform, projects, "HEAD")
        assert _names(selected) == ["alpha", "beta"]
        _run_git(repo, "checkout", "HEAD", "--", ".")

        # Deletion of a tracked file still affects its original member
        _run_git(repo, "rm", "packages/alpha/module.py")
        selected = select_changed_projects(platform, projects, "HEAD")
        assert _names(selected) == ["alpha", "beta"]
        _run_git(repo, "checkout", "HEAD", "--", ".")

        # A staged rename across members affects both the old and the new member
        _run_git(repo, "mv", "packages/alpha/module.py", "packages/beta/moved_module.py")
        selected = select_changed_projects(platform, projects, "HEAD")
        assert _names(selected) == ["alpha", "beta"]

    def test_invalid_reference(self, temp_dir):
        from hatch.utils.platform import Platform

        repo = temp_dir / "repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text("[project]\nname = 'root'\n")
        _run_git(repo, "init")
        _run_git(repo, "config", "--local", "user.name", "test")
        _run_git(repo, "config", "--local", "user.email", "test@example.com")
        _run_git(repo, "add", "-A")
        _run_git(repo, "commit", "-m", "baseline")

        project = FakeProject(repo, "root")
        with pytest.raises(ChangedSinceError, match="Invalid Git reference `does-not-exist`"):
            select_changed_projects(Platform(), [project], "does-not-exist")


class TestChangedSinceCli:
    def _create_workspace(self, hatch, temp_dir, *, dependencies=None):
        with temp_dir.as_cwd():
            result = hatch("new", "workspace-root")
            assert result.exit_code == 0, result.output

        workspace_root = temp_dir / "workspace-root"
        with (workspace_root / "pyproject.toml").open("a") as f:
            f.write(
                """
[tool.hatch.envs.default]
workspace.members = ["packages/*"]
"""
            )

        packages_dir = workspace_root / "packages"
        packages_dir.mkdir()
        with packages_dir.as_cwd():
            for project_name in ("member1", "member2"):
                result = hatch("new", project_name)
                assert result.exit_code == 0, result.output

        if dependencies:
            from hatch.project.core import Project

            for project_name, requirement_names in dependencies.items():
                member_path = packages_dir / project_name
                project = Project(member_path)
                config = dict(project.raw_config)
                config["project"]["dependencies"] = list(requirement_names)
                project.save_config(config)

        return workspace_root

    def _initialize_git(self, workspace_root):
        _run_git(workspace_root, "init")
        _run_git(workspace_root, "config", "--local", "user.name", "test")
        _run_git(workspace_root, "config", "--local", "user.email", "test@example.com")
        _run_git(workspace_root, "add", "-A")
        _run_git(workspace_root, "commit", "-m", "baseline")

    def test_requires_all_flag(self, hatch, temp_dir, helpers):
        with temp_dir.as_cwd():
            result = hatch("new", "my-app")
            assert result.exit_code == 0, result.output

        path = temp_dir / "my-app"
        with path.as_cwd():
            result = hatch("build", "--changed-since", "HEAD")

        assert result.exit_code == 1, result.output
        assert result.output == helpers.dedent(
            """
            The `--changed-since` option can only be used together with the `--all` flag
            """
        )

    @pytest.mark.requires_git
    def test_invalid_reference_aborts_before_building(self, hatch, temp_dir, helpers):
        workspace_root = self._create_workspace(hatch, temp_dir)
        self._initialize_git(workspace_root)

        with workspace_root.as_cwd():
            result = hatch("build", "--all", "--changed-since", "does-not-exist")

        assert result.exit_code == 1, result.output
        assert result.output == helpers.dedent(
            """
            Invalid Git reference `does-not-exist` passed to `--changed-since`
            """
        )
        assert not (workspace_root / "dist").is_dir()

    @pytest.mark.requires_git
    def test_no_changes_does_not_build_or_touch_artifacts(self, hatch, temp_dir):
        workspace_root = self._create_workspace(hatch, temp_dir)
        self._initialize_git(workspace_root)

        build_directory = workspace_root / "dist"
        build_directory.mkdir()
        sentinel = build_directory / "sentinel.txt"
        sentinel.write_text("keep me\n")

        with workspace_root.as_cwd():
            result = hatch("build", "--all", "--changed-since", "HEAD")

        assert result.exit_code == 0, result.output
        assert "No tracked file changes detected since `HEAD`, nothing to build" in result.output
        assert sentinel.is_file()
        # Only the sentinel exists, no build environments or artifacts were produced
        assert sorted(path.name for path in build_directory.iterdir()) == ["sentinel.txt"]

    @pytest.mark.requires_git
    @pytest.mark.requires_internet
    @pytest.mark.usefixtures("mock_backend_process")
    def test_only_changed_member_is_built(self, hatch, temp_dir):
        workspace_root = self._create_workspace(hatch, temp_dir)
        self._initialize_git(workspace_root)

        changed_file = workspace_root / "packages" / "member1" / "src" / "member1" / "__init__.py"
        changed_file.write_text('__version__ = "9000"\n')

        with workspace_root.as_cwd():
            result = hatch("build", "--all", "--changed-since", "HEAD")

        assert result.exit_code == 0, result.output
        artifacts = sorted(path.name for path in (workspace_root / "dist").iterdir())
        assert artifacts == [
            "member1-0.0.1-py3-none-any.whl",
            "member1-0.0.1.tar.gz",
        ]
        assert " member1 " in result.output
        assert " member2 " not in result.output

    @pytest.mark.requires_git
    @pytest.mark.requires_internet
    @pytest.mark.usefixtures("mock_backend_process")
    def test_dependent_members_are_built(self, hatch, temp_dir):
        workspace_root = self._create_workspace(hatch, temp_dir, dependencies={"member2": ["member1"]})
        self._initialize_git(workspace_root)

        changed_file = workspace_root / "packages" / "member1" / "src" / "member1" / "__init__.py"
        changed_file.write_text('__version__ = "9000"\n')

        with workspace_root.as_cwd():
            result = hatch("build", "--all", "--changed-since", "HEAD")

        assert result.exit_code == 0, result.output
        artifacts = sorted(path.name for path in (workspace_root / "dist").iterdir())
        assert artifacts == [
            "member1-0.0.1-py3-none-any.whl",
            "member1-0.0.1.tar.gz",
            "member2-0.0.1-py3-none-any.whl",
            "member2-0.0.1.tar.gz",
        ]
        assert " member1 " in result.output
        assert " member2 " in result.output
