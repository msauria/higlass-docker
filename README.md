# higlass-ie

Builds a docker container wrapping higlass-client and higlass-server in nginx,
adds support for running as a Galaxy interactive environment, and tests that
it works, and if there are no errors in the PR, pushes the image to
[DockerHub](https://hub.docker.com/r/msauria/higlass-ie/).

This builds on [higlass-docker](https://github.com/higlass/higlass-docker)
and is only suitable for use with [Galaxy](https://www.usegalaxy.org). Please
see [HiGlass](https://higlass.io) for more information.