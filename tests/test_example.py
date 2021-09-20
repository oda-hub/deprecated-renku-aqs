import subprocess
import shutil
import os

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
    
    return repo_dir


# on purpose from shell
def renku_cli(cmd: list, repo_dir: str, root_dir: str):
  
    subprocess.check_call(["renku"] + cmd, cwd=repo_dir, env=dict(
            {**os.environ,
             "PYTHONPATH": str(root_dir) + ":" + str(root_dir) + "/tests:" + os.environ.get('PYTHONPATH', "")}
        ))


def test_example_oda_repo_code_py(pytestconfig):
    repo_dir = fetch_example_oda_repo(fresh=True, reset=True)

    renku_cli(["run", "python", "example_code.py", "--output", "test-output.txt"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)

    renku_cli(["graph", "generate", "--force"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)

    renku_cli(["aqs", "params"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)

    renku_cli(["aqs", "kg", "push"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)
    
    #TODO:
    #renku aqs params
    #rdf2dot renku-aqs-test-case/subgraph.ttl  | dot -Tpng -o subgraph.png
    # add references to the workflow identity and location

def test_example_oda_repo_papermill(pytestconfig):
    repo_dir = fetch_example_oda_repo()

    renku_cli(["run", "papermill", "final-an.ipynb", "out.ipynb", "--output", "test-output.txt"], repo_dir=repo_dir, root_dir=pytestconfig.rootdir)