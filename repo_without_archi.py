import os
import csv
import subprocess
import time
from github import Github
from tqdm import tqdm

# ====== CONFIG ======
GITHUB_TOKEN = "your github token here"
CLONE_DIR = "/content/drive/MyDrive/verilog_repos_batch"
LOG_FILE = "/content/drive/MyDrive/cloned_repos_log.txt"
METADATA_CSV = "/content/drive/MyDrive/repo_metadata.csv"
UNKNOWN_LOG = "/content/drive/MyDrive/open_unknown_licenses.txt"

MAX_REPOS_TOTAL = 1000
MIN_STARS = 1
MIN_FORKS = 0
PER_PAGE = 50

# ✅ Only using open license keywords now
OPEN_LICENSE_KEYWORDS = [
    "license", "gnu", "gpl", "mit", "bsd", "apache", "mozilla",
    "lgpl", "eclipse", "open", "cc0", "public"
]

# ====== INIT ======
g = Github(GITHUB_TOKEN)
query = "language:Verilog"
os.makedirs(CLONE_DIR, exist_ok=True)

# Already cloned repos
downloaded_repos = set()
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        downloaded_repos = set(line.strip() for line in f)

# CSV setup
csv_file = open(METADATA_CSV, "w", newline="", encoding="utf-8")
csv_writer = csv.DictWriter(csv_file, fieldnames=[
    "name", "url", "stars", "forks", "language", "license", "description"])
csv_writer.writeheader()

# License check based only on keywords
def is_open_source_license(repo):
    if repo.license:
        spdx = repo.license.spdx_id or "Unknown"
        name = (repo.license.name or "").lower()
        if any(k in name for k in OPEN_LICENSE_KEYWORDS):
            with open(UNKNOWN_LOG, "a") as log:
                log.write(f"{repo.full_name} | {spdx} | {name}\n")
            return True
    return False

# ====== Fetch All Repos (Paginated) ======
repo_list = []
print("🔍 Fetching repos...")
for page in range(1, (MAX_REPOS_TOTAL // PER_PAGE) + 2):  # e.g. 20 pages for 1000 repos
    try:
        page_repos = g.search_repositories(query=query, sort="stars", order="desc").get_page(page - 1)
        if not page_repos:
            break
        repo_list.extend(page_repos)
        time.sleep(1)
    except Exception as e:
        print(f"[!] Page {page} error: {e}")
        break

print("🚀 Cloning up to", len(repo_list), "repos...")

# ====== Clone & Save Metadata ======
total_cloned = 0
skipped_license = 0
skipped_duplicate = 0
skipped_stars_forks = 0
failed_clones = 0

for repo in tqdm(repo_list, desc="Cloning Repos"):
    if total_cloned >= MAX_REPOS_TOTAL:
        break

    full_name = repo.full_name
    if full_name in downloaded_repos:
        skipped_duplicate += 1
        continue
    if repo.stargazers_count < MIN_STARS or repo.forks_count < MIN_FORKS:
        skipped_stars_forks += 1
        continue
    if not is_open_source_license(repo):
        skipped_license += 1
        continue

    try:
        target_path = os.path.join(CLONE_DIR, full_name.replace("/", "__"))
        subprocess.run(["git", "clone", repo.clone_url, target_path], check=True)
        with open(LOG_FILE, "a") as f:
            f.write(full_name + "\n")
        csv_writer.writerow({
            "name": full_name,
            "url": repo.html_url,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "language": repo.language,
            "license": repo.license.spdx_id if repo.license else "Unknown",
            "description": repo.description or ""
        })
        total_cloned += 1
    except subprocess.CalledProcessError:
        print(f"[!] Failed to clone: {repo.clone_url}")
        failed_clones += 1

csv_file.close()

# ====== Summary ======
print(f"\n✅ Done! Cloned {total_cloned} repositories into {CLONE_DIR}")
print(f"🔁 Already cloned (skipped): {skipped_duplicate}")
print(f"📉 Skipped due to stars/forks: {skipped_stars_forks}")
print(f"🔒 Skipped due to license: {skipped_license}")
print(f"⚠️  Clone failures: {failed_clones}")
