import os
import csv
import time
import subprocess
from github import Github
from tqdm import tqdm

# ========== CONFIGURATION ==========
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CLONE_DIR = "verilog_repos_new_batch"
LOG_FILE = "cloned_repos_log_new.txt"
METADATA_CSV = "repo_metadata_new.csv"
SKIPPED_LICENSE_LOG = "skipped_due_to_license_new.txt"

MIN_STARS = 1
MAX_REPOS_PER_YEAR = 1000  # GitHub API limit per query
OPEN_LICENSE_KEYWORDS = ["mit", "gpl", "apache", "bsd", "lgpl", "mpl", "epl", "cc0", "mozilla", "open"]

# ========== INIT ==========
os.makedirs(CLONE_DIR, exist_ok=True)
g = Github(GITHUB_TOKEN)

# ========== Helper Functions ==========
def is_open_source_license(repo):
    try:
        license_info = repo.get_license()
        if hasattr(license_info, "license") and license_info.license:
            spdx = (license_info.license.spdx_id or "").lower()
            name = (license_info.license.name or "").lower()
            if any(k in spdx for k in OPEN_LICENSE_KEYWORDS) or any(k in name for k in OPEN_LICENSE_KEYWORDS):
                return True
            else:
                with open(SKIPPED_LICENSE_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[SKIP] {repo.full_name} | SPDX: {spdx} | Name: {name}\n")
        else:
            with open(SKIPPED_LICENSE_LOG, "a", encoding="utf-8") as f:
                f.write(f"[SKIP] {repo.full_name} | No license object\n")
        return False
    except Exception as e:
        with open(SKIPPED_LICENSE_LOG, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] {repo.full_name} | License fetch error: {str(e)}\n")
        return False

def clone_repo(repo):
    target_path = os.path.join(CLONE_DIR, repo.full_name.replace("/", "__"))
    subprocess.run(["git", "clone", repo.clone_url, target_path], check=True)

# ========== Search Over Year Ranges ==========
def fetch_repos_by_year_range(start_year=2015, end_year=2025):
    total_cloned = 0
    downloaded_repos = set()

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            downloaded_repos = set(line.strip() for line in f)

    csv_file = open(METADATA_CSV, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        "name", "url", "stars", "forks", "language", "license", "description"])
    csv_writer.writeheader()

    for year in range(start_year, end_year + 1):
        query = f"language:Verilog created:{year}-01-01..{year}-12-31 stars:>={MIN_STARS}"
        print(f"\nSearching: {query}")
        try:
            results = g.search_repositories(query=query, sort="stars", order="desc")
            for repo in tqdm(results[:MAX_REPOS_PER_YEAR], desc=f"Processing {year}"):
                if repo.full_name in downloaded_repos:
                    continue
                if not is_open_source_license(repo):
                    continue

                try:
                    clone_repo(repo)
                    with open(LOG_FILE, "a") as f:
                        f.write(repo.full_name + "\n")
                    csv_writer.writerow({
                        "name": repo.full_name,
                        "url": repo.html_url,
                        "stars": repo.stargazers_count,
                        "forks": repo.forks_count,
                        "language": repo.language,
                        "license": repo.get_license().license.spdx_id if repo.get_license().license else "Unknown",
                        "description": repo.description or ""
                    })
                    total_cloned += 1
                except Exception as clone_error:
                    print(f"[!] Clone failed: {repo.full_name} | {clone_error}")

        except Exception as e:
            print(f"[!] Error for {year}: {e}")
            continue

    csv_file.close()
    print(f"\nDone! Total cloned: {total_cloned}")

# ========== Run ==========
if __name__ == "__main__":
    fetch_repos_by_year_range(2015, 2025)

