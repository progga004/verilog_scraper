# -*- coding: utf-8 -*-
import os
import csv
import subprocess
import time
from github import Github
from tqdm import tqdm

# ====== CONFIG ======
GITHUB_TOKEN = "token"
CLONE_DIR = "/home/ulabidez/pc/verilog_scraper/verilog_repos_batch"
LOG_FILE = "/home/ulabidez/pc/verilog_scraper/cloned_repos_log.txt"
METADATA_CSV = "/home/ulabidez/pc/verilog_scraper/repo_metadata.csv"
UNKNOWN_LOG = "/home/ulabidez/pc/verilog_scraper/open_unknown_licenses.txt"

MAX_REPOS_TOTAL = 1000
MIN_STARS = 1
MIN_FORKS = 0
PER_PAGE = 50

# ✅ Only using open license keywords now
OPEN_LICENSE_KEYWORDS = [
    "mit", "gpl", "apache", "bsd", "lgpl", "mpl", "epl", "cc0", "mozilla", "open"
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
# Safely fetch license info
license_info = None
try:
    license_info = repo.get_license()
except Exception:
    pass

if license_info and hasattr(license_info, "license") and license_info.license:
    license_str = license_info.license.spdx_id or "Unknown"
else:
    license_str = "Unknown"

csv_writer = csv.DictWriter(csv_file, fieldnames=[
    "name", "url", "stars", "forks", "language", "license", "description"])
csv_writer.writeheader()

# License check based only on keywords
def is_open_source_license(repo):
    try:
        license_info = repo.get_license()

        # Defensive fallback: handle raw dicts or missing attributes
        spdx = ""
        name = ""

        # New safe check
        if hasattr(license_info, "license") and license_info.license:
            spdx = (license_info.license.spdx_id or "").lower()
            name = (license_info.license.name or "").lower()
        elif isinstance(license_info, dict):
            spdx = (license_info.get("license", {}).get("spdx_id") or "").lower()
            name = (license_info.get("license", {}).get("name") or "").lower()
        else:
            with open("skipped_due_to_license.txt", "a", encoding="utf-8") as f:
                f.write(f"[SKIP] {repo.full_name} | License structure unknown\n")
            return False

        if any(k in spdx for k in OPEN_LICENSE_KEYWORDS) or any(k in name for k in OPEN_LICENSE_KEYWORDS):
            return True
        else:
            with open("skipped_due_to_license.txt", "a", encoding="utf-8") as f:
                f.write(f"[SKIP] {repo.full_name} | SPDX: {spdx} | Name: {name}\n")
            return False

    except Exception as e:
        with open("skipped_due_to_license.txt", "a", encoding="utf-8") as f:
            f.write(f"[ERROR] {repo.full_name} | License fetch error: {str(e)}\n")
        return False
    

# ====== Fetch All Repos (Paginated) ======
repo_list = []
print("Fetching repos...")
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

print("Cloning up to", len(repo_list), "repos...")

# ====== Clone & Save Metadata ======
total_cloned = 0
skipped_license = 0
skipped_duplicate = 0
skipped_stars_forks = 0
failed_clones = 0

for partial_repo in tqdm(repo_list, desc="Cloning Repos"):
    if total_cloned >= MAX_REPOS_TOTAL:
        break

    try:
        repo = g.get_repo(partial_repo.full_name)  # Upgrade to full object
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
        if repo.size == 0:
            continue

        # Clone
        target_path = os.path.join(CLONE_DIR, full_name.replace("/", "__"))
        subprocess.run(["git", "clone", repo.clone_url, target_path], check=True)

        # Save logs
        with open(LOG_FILE, "a") as f:
            f.write(full_name + "\n")
        csv_writer.writerow({
            "name": full_name,
            "url": repo.html_url,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "language": repo.language,
            "license": license_str,
            "description": repo.description or ""
        })
        total_cloned += 1

    except subprocess.CalledProcessError:
        print(f"[!] Failed to clone: {repo.clone_url}")
        failed_clones += 1
    except subprocess.TimeoutExpired:
        print(f"[!] Clone timeout: {repo.clone_url}")
        failed_clones += 1
    except Exception as e:
        # Use partial_repo.full_name here because repo may be undefined
        print(f"[!] Unexpected error on repo {full_name}: {e}")
        failed_clones += 1

csv_file.close()

# ====== Summary =====
print(f"\nDone! Cloned {total_cloned} repositories into {CLONE_DIR}")
print(f"Already cloned (skipped): {skipped_duplicate}")
print(f"Skipped due to stars/forks: {skipped_stars_forks}")
print(f"Skipped due to license: {skipped_license}")
print(f"Clone failures: {failed_clones}")

