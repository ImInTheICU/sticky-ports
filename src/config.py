# config.py
import yaml

with open("config.yaml") as f:
    CONFIG = yaml.safe_load(f)
