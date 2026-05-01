from setuptools import setup

setup(
    name="sportpulse",
    version="1.0.0",
    description="Live sports CLI dashboard — NBA, NHL, AFL, NFL",
    py_modules=["sportpulse"],
    install_requires=["requests>=2.28.0"],
    entry_points={
        "console_scripts": [
            "sportpulse=sportpulse:cli_entry",
        ],
    },
    python_requires=">=3.8",
)
