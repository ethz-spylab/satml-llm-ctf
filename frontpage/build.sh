#!/bin/bash
trash public/*
for file in content/*.md; do
    pandoc $file -o public/$(basename $file .md).html --template=template.html --katex
done
cp -r static public/
