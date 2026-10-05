FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# the image's Yarn apt source has an expired key and breaks apt-get for the
# features; we don't use Yarn
RUN rm -f /etc/apt/sources.list.d/yarn.list
