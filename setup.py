from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [line.strip() for line in f if line.strip()]

setup(
    name="transport_logistics",
    version="1.0.0",
    description="Transport, Fuel, Tyre and Truck Management with Cost Analysis for ERPNext 16",
    author="Wycliffs",
    author_email="admin@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
