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
jp_proxy_widget/_version.py
js/package.json
js/lib/proxy_implementation.js
jp_proxy_widget/proxy_widget.py
```

git add the _version.py file and git commit.

```
git add jp_proxy_widget/_version.py
git add js/package.json
git add js/lib/proxy_implementation.js
git add jp_proxy_widget/proxy_widget.py
git commit -m "new release"

git tag -a X.X.X -m 'comment'
git push
git push --tags
```

Upload to `pip`

`python setup.py sdist upload`

`python setup.py bdist_wheel upload`

- To release a new version of jp_proxy_widget on NPM:

```
# clean out the `dist` and `node_modules` directories
cd js
git clean -fdx
npm install
npm publish
```