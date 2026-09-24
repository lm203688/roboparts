#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.pipeline.stages — 领域算子集合。

每个子模块声明自己领域的所有算子，通过 @operator 装饰器挂到全局表。
stages 是**声明**层，不放 DAG 定义；DAG 定义放在对应 build_*.py 或 pipeline_def_*.py。
"""
