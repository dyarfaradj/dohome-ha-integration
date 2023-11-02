# Use an official Home Assistant base image for your architecture
ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set environment variables, including the timezone
ENV LANG C.UTF-8
ENV TERM xterm
ENV TZ Europe/Amsterdam


# Copy the addon directory (including run.sh) into the Docker image
COPY . /addons/dohome_addon/

# Set the working directory
WORKDIR /addons/dohome_addon

# Expose any required ports (if applicable)
EXPOSE 80

# Make the run.sh script executable
RUN chmod +x run.sh

# Define the command to start your addon
CMD [ "bash", "/addons/dohome_addon/run.sh" ]