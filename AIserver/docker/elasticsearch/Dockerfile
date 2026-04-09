FROM docker.elastic.co/elasticsearch/elasticsearch:9.3.0

# Install IK analyzer plugin at build time so it persists across container restarts.
RUN /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch https://get.infini.cloud/elasticsearch/analysis-ik/9.3.0
