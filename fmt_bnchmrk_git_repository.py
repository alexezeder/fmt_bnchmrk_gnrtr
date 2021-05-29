import glob
import os
import shutil
import tempfile

import git


class FmtBnchmrkRepo:
    pages_branch_name: str = 'gh-pages'

    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = git.Repo.clone_from('git@github.com:alexezeder/fmt_bnchmrk.git', self.temp_dir.name)
        origin_refs = self.repo.remotes['origin'].refs
        if FmtBnchmrkRepo.pages_branch_name in origin_refs:
            self.repo.remotes['origin'].fetch(refspec='{}:{}'.format(FmtBnchmrkRepo.pages_branch_name,
                                                                     FmtBnchmrkRepo.pages_branch_name))

    def get_directory(self) -> str:
        return self.temp_dir.name

    def get_commit_hash(self) -> str:
        return self.repo.commit('HEAD').hexsha

    def commit_pages(self, pages_directory: str):
        hash_before = self.repo.commit('HEAD').hexsha

        heads = self.repo.heads
        if FmtBnchmrkRepo.pages_branch_name in heads:
            pages_branch = heads[FmtBnchmrkRepo.pages_branch_name]
            self.repo.git.branch('-D', pages_branch)

        self.repo.git.checkout('--orphan', FmtBnchmrkRepo.pages_branch_name)
        self.repo.head.reset(index=True, working_tree=True)

        for filename in glob.glob(os.path.join(pages_directory, '*.*')):
            shutil.copy(filename, self.temp_dir.name)
            self.repo.index.add([os.path.join(self.temp_dir.name, os.path.basename(filename))])

        actor = git.Actor('Page Committer Bot', 'kill@all.humans')
        self.repo.index.commit('update pages', author=actor, committer=actor)
        self.repo.remotes['origin'].push(
            refspec='{}:{}'.format(FmtBnchmrkRepo.pages_branch_name, FmtBnchmrkRepo.pages_branch_name), force=True)

        self.repo.head.reference = self.repo.commit(hash_before)
        self.repo.head.reset(index=True, working_tree=True)
        hash_after = self.repo.commit('HEAD').hexsha
        assert hash_before == hash_after
