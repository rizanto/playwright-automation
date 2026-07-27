import os
import sys

# Masukkan folder parent (root) ke dalam system path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import scrape_ksa

def run_scrape(auto_profile_idx=None):
    return scrape_ksa.run_scrape_ksa(commodity="Padi", auto_profile_idx=auto_profile_idx)

if __name__ == "__main__":
    run_scrape()
