- To release a new version of jp_proxy_widget on PyPI:

For fun and safety first snapshot the current state of the working folder
because some commands below may delete files you forgot you wanted
to keep (it happens).

```bash
mkdir -p ~/snapshots/jp_proxy_widget
cp -rf * ~/snapshots/jp_proxy_widget
```

Update _version.py (set release version, remove 'dev').

Also bump the version information in 

```
js/package.json
js/lib/proxy_implementation.js
jp_proxy_widget/proxy_widget.py
```

git add the _version.py file and git commit.

`python setup.py sdist upload`

`python setup.py bdist_wheel upload`

`git tag -a X.X.X -m 'comment'`

Update _version.py (add 'dev' and increment minor)
git add and git commit
git push
git push --tags

- To release a new version of jp_proxy_widget on NPM:

```
# clean out the `dist` and `node_modules` directories
git clean -fdx
npm install
npm publish
```