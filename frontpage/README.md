# Installing Pandoc and Node.js

On Arch Linux:
```shell
sudo pacman -S pandoc nodejs
```

# Building the site

**build.sh**
```shell
trash public/*
for file in content/*.md; do
    pandoc $file -o public/$(basename $file .md).html --template=template.html --katex
done
cp -r static public/
```

**serve.sh**
```shell
npx http-server public
```

# Deploying to GitHub Pages

This doesn't work, we haven't deployed on GitHub pages but in the app

**publish.sh**
```shell
trash public/*
for file in content/*.md; do
    pandoc $file -o public/$(basename $file .md).html --template=template.html --katex
done
cp -r static public/
cd public
git add *
git commit -m "Rebuilding site $(date)"
git push origin HEAD:master
```

# How to add various CSS things on the page
[mvp.css](https://andybrewer.github.io/mvp/) has everything that is supported out of the box.
