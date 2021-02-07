import setuptools

if __name__ == "__main__":
	setuptools.setup(name='kekmonitors',
                  version='0.1',
                  description='Open source codebase for development of sneakers monitors',
                  url='https://github.com/berton7/kek-monitors',
                  author='berton7',
                  author_email='francy.berton99@gmail.com',
                  license='MIT',
                  packages=setuptools.find_packages(),
                  python_requires=">=3.6",
                  install_requires=[
                      "discord.py",
                      "tornado",
                      "requests",
                      "pycurl",
                      "watchdog",
                      "pymongo",
                      "aiohttp[speedups]" # needed for discord
                  ],
                  zip_safe=False)
