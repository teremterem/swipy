# swipy

## Run docker-compose locally

```
ngrok http 80
```

After that set the following env var in `docker.env` file:
```
SWIPY_WEBHOOKS_BASE_URL=https://xxxxxxxxxxxx.ngrok.io/core
```

```
docker-compose --env-file docker.env up -d
```
**NOTE:** Before running `docker-compose` command above make sure you are NOT in `pipenv shell`. Otherwise env var
values from `.env` will override the ones defined in `docker.env`.

## Prepare AWS EC2

```
sudo yum update -y
sudo yum install git -y

git clone git@github.com:teremterem/swipy.git


# https://gist.github.com/npearce/6f3c7826c7499587f00957fee62f8ee9

sudo amazon-linux-extras install docker
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo chkconfig docker on
```
```
# https://docs.docker.com/compose/install/
# ...
```
```
sudo reboot

python3 --version && docker -v && docker-compose -v
```

## Run docker-compose in AWS EC2

After checking out the repo make sure to fix [permissions](
https://rasa.com/docs/rasa-x/installation-and-setup/install/docker-compose#permissions-on-mounted-directories):
```
cd swipy/
```
```
sudo chgrp -R root * && sudo chmod -R 770 *
```

Create `.env` file (TODO instructions).

Then run the following:
```
docker-compose -f docker-compose.yml -f docker-compose.aws.yml up -d
```

## Installation (obsolete?)
```
pipenv sync
pipenv run python -m spacy download en_core_web_trf
```

## Misc notes

### macOS Big Sur

```
export SYSTEM_VERSION_COMPAT=1
```
