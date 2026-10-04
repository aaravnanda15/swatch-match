FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# The base image lists the Yarn apt repository, whose signing key is no longer
# valid; that makes apt-get fail for the features in devcontainer.json.
# Swatch Match does not use Yarn, so drop that source.
RUN rm -f /etc/apt/sources.list.d/yarn.list
