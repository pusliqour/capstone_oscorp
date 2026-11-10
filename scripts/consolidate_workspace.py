"""Consolidate known local Jiran folders without deleting their contents.

Moves use rename on this Mac and leave compatibility symlinks at every previous
path. Private data and nested reference/deployment repositories stay outside the
public source index. The private journal records every relocation.
"""
import json
import os
from pathlib import Path

HOME_DIR=Path.home()
CANONICAL=HOME_DIR/'Projects/Jiran'
OLD=HOME_DIR/'Projects/ISDIA'

def consolidate():
    if not CANONICAL.exists():
        if not (OLD/'.git').exists():raise RuntimeError('Expected the existing Jiran source checkout at Projects/ISDIA')
        ignore=OLD/'.gitignore'
        ignore.write_text(ignore.read_text()+'\n# Consolidated local material; never publish credentials, datasets or nested repos\n/.private/\n/Private\n/.deploy/\n/Deployment\n')
        OLD.rename(CANONICAL)
        OLD.symlink_to(CANONICAL,target_is_directory=True)
    elif not OLD.is_symlink() or OLD.resolve()!=CANONICAL.resolve():
        raise RuntimeError('Canonical target already exists without the expected compatibility link')
    private=CANONICAL/'.private';private.mkdir(exist_ok=True,mode=0o700);private.chmod(0o700)
    deploy=CANONICAL/'.deploy';deploy.mkdir(exist_ok=True)
    for label,target in [('Private',private),('Deployment',deploy)]:
        link=CANONICAL/label
        if not link.exists():link.symlink_to(target,target_is_directory=True)
        elif not link.is_symlink() or link.resolve()!=target:raise RuntimeError('Unexpected existing folder: '+str(link))
    plan=[
      (HOME_DIR/'Documents/Jiran',private/'operator'),
      (HOME_DIR/'Downloads/Jiran.zip',private/'archives/Jiran-user-20261110.zip'),
      (HOME_DIR/'Downloads/Jiran-recovery-20261110',private/'recovery/20261110'),
      (HOME_DIR/'Downloads/Jiran',private/'sources/received-spreadsheets'),
      (HOME_DIR/'Projects/jiran-ml',private/'reference/original-ml-repository'),
      (HOME_DIR/'Projects/ISDIA-pages-demo',private/'reference/legacy-pages-preview'),
      (HOME_DIR/'Projects/jiran-pages-live',deploy/'pages'),
      (HOME_DIR/'Desktop/GitHub-Export-2026-11-03/jiran',private/'history/20261103-github-export'),
      (HOME_DIR/'Desktop/GitHub-Export-2026-11-03/jiran.zip',private/'archives/github-export-20261103.zip'),
      (HOME_DIR/'Desktop/Three-Projects-GitHub-Ready-2026-11-03/staging/JIRAN',private/'history/20261103-staging'),
    ]
    journal=private/'consolidation-manifest.json'
    records=json.loads(journal.read_text()) if journal.exists() else []
    for source,target in plan:
        if source.is_symlink() and source.resolve()==target.resolve():continue
        if not source.exists():print('Missing, left unchanged:',source);continue
        if target.exists():raise RuntimeError('Refusing to overwrite '+str(target))
        target.parent.mkdir(parents=True,exist_ok=True)
        is_directory=source.is_dir()
        source.rename(target)
        source.symlink_to(target,target_is_directory=is_directory)
        records.append({'previous_path':str(source),'canonical_path':str(target),'kind':'directory' if is_directory else 'file','previous_path_is_compatibility_symlink':True})
        journal.write_text(json.dumps(records,indent=2))
        print(source,'->',target)
    print('Canonical workspace:',CANONICAL)
    print('No content deleted; old paths remain compatible.')

if __name__=='__main__':consolidate()
