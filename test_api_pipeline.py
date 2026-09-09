#!/usr/bin/env python3

import time
import requests
from datetime import datetime

# =========================
# CONFIG
# =========================

OWNER = "liqinsg"
REPO = "fx_monte_carlo"
WORKFLOW = "mc_daily.yml"

GITHUB_TOKEN = "YOUR_GITHUB_PAT"

PAIR = "EURUSD"

# =========================
# HEADERS
# =========================

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


# =========================
# TRIGGER WORKFLOW
# =========================

def trigger_workflow():

    url = (
        f"https://api.github.com/repos/"
        f"{OWNER}/{REPO}/actions/workflows/"
        f"{WORKFLOW}/dispatches"
    )

    r = requests.post(
        url,
        headers=HEADERS,
        json={"ref": "main"}
    )

    r.raise_for_status()

    print("✅ Workflow triggered")


# =========================
# WAIT FOR COMPLETION
# =========================

def get_latest_run():

    url = (
        f"https://api.github.com/repos/"
        f"{OWNER}/{REPO}/actions/workflows/"
        f"{WORKFLOW}/runs"
    )

    r = requests.get(url, headers=HEADERS)

    r.raise_for_status()

    return r.json()["workflow_runs"][0]


def wait_for_completion(timeout=900):

    print("⏳ Waiting for workflow...")

    start = time.time()

    while time.time() - start < timeout:

        run = get_latest_run()

        status = run["status"]
        conclusion = run["conclusion"]

        print(
            f"status={status} "
            f"conclusion={conclusion}"
        )

        if status == "completed":

            if conclusion != "success":
                raise RuntimeError(
                    f"Workflow failed: {conclusion}"
                )

            print("✅ Workflow complete")
            return

        time.sleep(20)

    raise TimeoutError("Workflow timeout")


# =========================
# FETCH RESULT
# =========================

def fetch_result():

    today = datetime.utcnow()

    y = today.strftime("%Y")
    m = today.strftime("%m")
    d = today.strftime("%d")

    url = (
        "https://liqinsg.github.io/"
        "fx_monte_carlo/"
        f"api/{y}/{m}/{d}/{PAIR}.json"
    )

    print(f"Downloading:\n{url}")

    r = requests.get(url)

    r.raise_for_status()

    data = r.json()

    print("\n========== API RESULT ==========\n")

    print(data)

    print("\n================================\n")

    return data


# =========================
# DELETE FILE
# =========================

def github_delete(path):

    get_url = (
        f"https://api.github.com/repos/"
        f"{OWNER}/{REPO}/contents/{path}"
    )

    r = requests.get(
        get_url,
        headers=HEADERS
    )

    if r.status_code == 404:
        print(f"Skip {path}")
        return

    r.raise_for_status()

    sha = r.json()["sha"]

    payload = {
        "message": f"cleanup {path}",
        "sha": sha
    }

    r = requests.delete(
        get_url,
        headers=HEADERS,
        json=payload
    )

    r.raise_for_status()

    print(f"🗑 Deleted {path}")


# =========================
# CLEANUP
# =========================

def cleanup():

    today = datetime.utcnow()

    y = today.strftime("%Y")
    m = today.strftime("%m")
    d = today.strftime("%d")

    targets = [

        f"api/{y}/{m}/{d}/{PAIR}.json",
        f"api/{y}/{m}/{d}/all.json",
        f"api/latest/{PAIR}.json",
        "api/latest/all.json"
    ]

    for target in targets:
        github_delete(target)

    print("✅ Cleanup complete")


# =========================
# MAIN
# =========================

def main():

    trigger_workflow()

    wait_for_completion()

    fetch_result()

    cleanup()


if __name__ == "__main__":
    main()

