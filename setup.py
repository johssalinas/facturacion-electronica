from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

setup(
	name="facturacion_electronica",
	version="0.0.1",
	description="Facturacion electronica Colombia (Factus API) para ERPNext",
	author="Salsamentaria",
	author_email="admin@salsamentaria.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
