#
# OpenJDK Java 8 JRE Dockerfile
#

# Pull base image.
FROM ubuntu

# Install Java.
RUN \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-8-jre && \
  rm -rf /var/lib/apt/lists/*

# Define commonly used JAVA_HOME variable
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# Define working directory.
WORKDIR /data

COPY hodoku.jar /data/

# Define default command.
ENTRYPOINT ["java", "-Xmx512m", "-jar", "/data/hodoku.jar"]
CMD []
