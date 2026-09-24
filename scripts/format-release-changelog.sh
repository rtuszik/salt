#!/bin/sh
set -eu

tag="v$1"
old_head=$(git rev-parse HEAD)
tag_target=$(git rev-parse "refs/tags/$tag")

if [ "$tag_target" != "$old_head" ]; then
    echo "Expected lightweight tag $tag at HEAD" >&2
    exit 1
fi

if ! git diff --cached --quiet; then
    echo "Refusing to amend a version commit with staged changes" >&2
    exit 1
fi

rumdl fmt --config 'MD013.reflow = true' CHANGELOG.md
rumdl check CHANGELOG.md
if git diff --quiet -- CHANGELOG.md; then
    exit 0
fi

git add -- CHANGELOG.md
git commit --amend --no-edit
git update-ref "refs/tags/$tag" HEAD "$old_head"
