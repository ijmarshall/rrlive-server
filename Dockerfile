#############################
# Non-DeepLearning Dockerfile 09
# 2021 Docker Version:v20.10.7
# Frank Soboczenski
# 2021, December
#############################

#update nvidia repo keys to use the cuda image
#FROM nvidia/cuda:11.4.0-base-ubuntu20.04 

FROM ubuntu:20.04

LABEL authors="frank.soboczenski@gmail.com"

# Install some basic utilities
RUN apt-get update && apt-get install -y \
    ca-certificates \
    sudo \
    bash \
    git \
    bzip2 \
    libx11-6 \
    openssl \
    sqlite \
    nano \
    curl \
    libpq-dev \
    python-dev \
    gcc \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create directories & set default directory
RUN mkdir /app
COPY . /app
WORKDIR /app

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos '' --shell /bin/bash user \
 && chown -R user:user /app
RUN echo "user ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-user
USER user

# All users can use /home/user as their home directory
ENV HOME=/home/user
RUN chmod 777 /home/user

# Install Miniconda and Python 3.8
ENV CONDA_AUTO_UPDATE_CONDA=false
ENV PATH=/home/user/miniconda/bin:$PATH
RUN curl -sLo ~/miniconda.sh https://repo.continuum.io/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh \
 && chmod +x ~/miniconda.sh \
 && ~/miniconda.sh -b -p ~/miniconda \
 && rm ~/miniconda.sh \
 && conda install -y python==3.8 \
 && conda clean -ya

# Installing neccessary libraries
RUN pip install -r requirements.txt

# Due to crediential manual initialisation otherwise enable:
# CMD ["uvicorn", "app.main:app", "--reload", "--port 8912"]
CMD tail -f /dev/null
