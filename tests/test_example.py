import subprocess
import shutil
import os
import pytest

__this_dir__ = os.path.join(os.path.abspath(os.path.dirname(__file__)))


# make fixture
def fetch_example_oda_repo(fresh=False, reset=True) -> str:
    repo_name = "renku-aqs-test-case"
    repo_dir = repo_name

    if os.path.exists(repo_dir):
        if fresh:
            shutil.rmtree(repo_dir)
        else:
            if reset:
                subprocess.check_call(
                    ["git", "reset", "--hard"],
                    cwd=repo_dir
                )        
                subprocess.check_call(
                    ["git", "clean", "-f", "-d"],
                    cwd=repo_dir
                )        
            
            return repo_dir

    subprocess.check_call(
        ["git", "clone", f"git@github.com:volodymyrss/{repo_name}.git", repo_dir]
    )
    subprocess.check_call(
        ["git", "lfs", "install", "--local"],
        cwd=repo_dir
    )
    subprocess.check_call(
        ["renku", "migrate"],
        cwd=repo_dir
    )

    return repo_dir


def env_fixture(root_dir: str):
    return dict(
        {
            **os.environ,
            "PYTHONPATH": str(root_dir) + ":" + str(root_dir) + "/tests:" + os.environ.get('PYTHONPATH', "")
        }
    )


# on purpose from shell
def run_renku_cli(cmd: list, repo_dir: str, root_dir: str):

    return subprocess.check_call(["renku"] + cmd, cwd=repo_dir, env=env_fixture(root_dir))


def test_example_oda_repo_code_py(pytestconfig):
    repo_dir = fetch_example_oda_repo()

    run_renku_cli(["run", "python", "example_code.py", "--output", "test-output.txt"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)

    #TODO:
    #renku aqs params
    #rdf2dot renku-aqs-test-case/subgraph.ttl  | dot -Tpng -o subgraph.png
    # add references to the workflow identity and location


def test_example_oda_repo_papermill(pytestconfig):
    repo_dir = fetch_example_oda_repo(fresh=True)

    ret_code = run_renku_cli(["run", "papermill", "final-an.ipynb", "out.ipynb"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)

    assert ret_code == 0


def test_example_cli_display(pytestconfig):
    repo_dir = fetch_example_oda_repo(fresh=True)

    ret_code = run_renku_cli(["run", "papermill", "final-an.ipynb", "out.ipynb"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)
    assert ret_code == 0

    ret_code = run_renku_cli(["aqs", "display"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)
    assert ret_code == 0


@pytest.mark.parametrize('input_notebook', ['final-an.ipynb', None])
def test_example_cli_display_no_oda_info(pytestconfig, monkeypatch, input_notebook):
    repo_dir = fetch_example_oda_repo(fresh=True)

    ret_code = run_renku_cli(["run", "papermill", "final-an.ipynb", "out.ipynb"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)
    assert ret_code == 0

    args = ["aqs", "display", "--no-oda-info"]
    if input_notebook is not None:
        args.extend(('--input-notebook', input_notebook))

    ret_code = run_renku_cli(args, repo_dir=repo_dir, root_dir=pytestconfig.rootdir)
    assert ret_code == 0
