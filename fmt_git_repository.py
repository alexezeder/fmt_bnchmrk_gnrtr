import tempfile
from typing import List

import git

import classes


class FmtRepo:
    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = git.Repo.clone_from('https://github.com/fmtlib/fmt.git', self.temp_dir.name)

        self.repo.head.reference = self.repo.commit('HEAD')
        self.repo.head.reset(index=True, working_tree=True)
        assert self.repo.head.is_detached

    def get_directory(self) -> str:
        return self.temp_dir.name

    def update(self):
        origin = self.repo.remotes.origin
        origin.fetch(refspec='master:master')

    def get_available_commits(self) -> List[classes.Commit]:
        amount: int = 50
        offset: int = 0
        available_commits: List[classes.Commit] = list()
        while True:
            commits = list(self.repo.iter_commits('master', max_count=amount, skip=offset))
            if len(commits) == 0:
                break
            for commit in commits:
                available_commits.append(classes.Commit(commit.hexsha, commit.committed_date))
            offset += amount
        max_index: int = len(available_commits) - 1
        for index, commit in enumerate(available_commits):
            commit.ID = max_index - index
        return available_commits[:classes.commits_number_limit]

    def set_current_commit(self, commit: str):
        self.repo.head.reference = self.repo.commit(commit)
        self.repo.head.reset(index=True, working_tree=True)

    def get_commit_message(self, commit_hash: str) -> str:
        commit = self.repo.commit(commit_hash)
        return commit.message
