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

## Run docker-compose in AWS EC2

```
docker-compose -f docker-compose.yml -f docker-compose.aws.yml --env-file docker-aws.env up -d
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
