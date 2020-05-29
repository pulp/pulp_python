import argparse
import os
import textwrap

from git import Repo


REDMINE_QUERY_URL = "https://pulp.plan.io/issues?set_filter=1&status_id=*&issue_id="
release_path = os.path.dirname(os.path.abspath(__file__))
plugin_path = release_path
if ".travis" in release_path:
    plugin_path = os.path.dirname(release_path)

version = {}
with open(f"{plugin_path}/pulp_python/__init__.py") as fp:
    version_line = [line for line in fp.readlines() if "__version__" in line][0]
    exec(version_line, version)
release_version = version["__version__"].replace(".dev", "")

to_close = []
for filename in os.listdir(f"{plugin_path}/CHANGES"):
    if filename.split(".")[0].isdigit():
        to_close.append(filename.split(".")[0])
issues = ",".join(to_close)

helper = textwrap.dedent(
    """\
        Start the release process.

        Example:
            setup.py on plugin before script:
                version="2.0.dev"
                requirements = ["pulpcore>=3.4"]


            $ python .travis/realease.py minor 4.0 4.1

            setup.py on plugin after script:
                version="2.1.dev"
                requirements = ["pulpcore>=4.0,<4.1"]

    """
)
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=helper)

parser.add_argument(
    "release_type", type=str, help="Whether the release should be major, minor or patch.",
)

parser.add_argument(
    "--lower", type=str, required=False, help="Lower bound of pulpcore requirement.",
)

parser.add_argument(
    "--upper", type=str, required=False, help="Upper bound of pulpcore requirement.",
)

args = parser.parse_args()

release_type = args.release_type

if "pulpcore" not in release_path:
    lower_pulpcore_version = args.lower
    upper_pulpcore_version = args.upper

print("\n\nHave you checked the output of: $towncrier --version x.y.z --draft")
print(f"\n\nRepo path: {plugin_path}")
repo = Repo(plugin_path)
git = repo.git

git.checkout("HEAD", b=f"release_{release_version}")

# First commit: changelog
os.system(f"towncrier --yes --version {release_version}")
git.add("CHANGES.rst")
git.add("CHANGES/*")
git.commit("-m", f"Building changelog for {release_version}\n\n[noissue]")

# Second commit: release version
with open(f"{plugin_path}/requirements.txt", "rt") as setup_file:
    setup_lines = setup_file.readlines()

with open(f"{plugin_path}/requirements.txt", "wt") as setup_file:
    for line in setup_lines:
        if "pulpcore" in line and "pulpcore" not in release_path:
            line = f"pulpcore>={lower_pulpcore_version},<{upper_pulpcore_version}\n"

        setup_file.write(line)

os.system("bump2version release --allow-dirty")

plugin_name = plugin_path.split("/")[-1]
git.add(f"{plugin_path}/{plugin_name}/__init__.py")
git.add(f"{plugin_path}/setup.py")
git.add(f"{plugin_path}/requirements.txt")
git.add(f"{plugin_path}/.bumpversion.cfg")
git.commit("-m", f"Releasing {release_version}\n\n[noissue]")

sha = repo.head.object.hexsha
short_sha = git.rev_parse(sha, short=7)

# Third commit: bump to .dev
with open(f"{plugin_path}/requirements.txt", "wt") as setup_file:
    for line in setup_lines:
        if "pulpcore" in line and "pulpcore" not in release_path:
            line = f"pulpcore>={lower_pulpcore_version}\n"

        setup_file.write(line)

os.system(f"bump2version {release_type} --allow-dirty")

version = {}
with open(f"{plugin_path}/pulp_python/__init__.py") as fp:
    version_line = [line for line in fp.readlines() if "__version__" in line][0]
    exec(version_line, version)
new_dev_version = version["__version__"]


git.add(f"{plugin_path}/{plugin_name}/__init__.py")
git.add(f"{plugin_path}/setup.py")
git.add(f"{plugin_path}/requirements.txt")
git.add(f"{plugin_path}/.bumpversion.cfg")
git.commit("-m", f"Bump to {new_dev_version}\n\n[noissue]")

print(f"\n\nRedmine query of issues to close:\n{REDMINE_QUERY_URL}{issues}")
print(f"Release commit == {short_sha}")
print(f"All changes were committed on branch: release_{release_version}")
