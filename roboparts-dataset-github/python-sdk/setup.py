from setuptools import setup, find_packages

setup(
    name="roboparts",
    version="1.0.0",
    description="RoboParts Python SDK - 仿生机器人零部件数据API客户端",
    author="RoboParts",
    author_email="support@roboparts.cc",
    url="https://roboparts.cc",
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
