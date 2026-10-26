#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish the ModelScope staging folder to modelscope.cn via SDK.

Token is read from MODELSCOPE_API_TOKEN (never written to disk).
Repo: roboparts-sync (dataset), created under the authenticated user's namespace.
"""
import os
import sys

from modelscope.hub.api import HubApi, ModelScopeConfig

TOKEN = os.environ.get('MODELSCOPE_API_TOKEN')
if not TOKEN:
    sys.exit('ERROR: set MODELSCOPE_API_TOKEN env var first')
REPO = 'roboparts-sync'
STAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'modelscope_staging')

api = HubApi()
api.login(TOKEN)                      # saves cookies + user info
uname, uemail = ModelScopeConfig.get_user_info()
print('logged in as:', uname, uemail)

repo_id = f'{uname}/{REPO}'
# create dataset (public, CC BY 4.0). visibility=5 == PUBLIC in ModelScope.
try:
    res = api.create_dataset(
        dataset_name=REPO,
        namespace=uname,
        visibility=5,
        license='CC-BY-4.0',
        chinese_name='仿生机器人零部件结构化数据集',
    )
    print('create_dataset ->', res)
except Exception as e:
    print('create_dataset skipped/exists:', repr(e)[:240])

print('uploading', STAGE, '->', repo_id)
api.upload_folder(repo_id=repo_id, folder_path=STAGE, repo_type='dataset')
print('UPLOAD_DONE', repo_id)
