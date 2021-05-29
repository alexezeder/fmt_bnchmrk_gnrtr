## Generator of [{fmt}](https://github.com/fmtlib/fmt) benchmark results

This project creates the nice output for [fmt_bnchmrk](https://github.com/alexezeder/fmt_bnchmrk) - just 
[check it out]().

### How to run

**First of all, I strongly recommend you to not run this project on your machine yet. But you can do this at your own
risk.**

These packages should be installed in your system:

* `git`
* `python3` and `python3-pip` and `python3-venv`
* `docker`
* `sqlite3`

Use `venv` and `pip` to install dependencies without polluting system.
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r /generator/requirements.txt
```

Current workflow of the `main.py` script (which is the entrypoint by the way):

* clone fmt_bnchmrk
* clone {fmt} repo
* initialize docker and build all runners from `runners` folder (currently only `gcc-11`)
* prepare SQLite DB for the current config
* while one of last 100 commits of {fmt} or newer:
  * run task in docker for this commit
  * upload results to fmt_bnchmrk Pages

Feel free to open issues and PRs.
