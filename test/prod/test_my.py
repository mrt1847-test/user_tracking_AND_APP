# test_features.py
from pytest_bdd import scenarios

# 특정 feature 파일만 로드
scenarios("../../features/prod/my_tracking.feature")