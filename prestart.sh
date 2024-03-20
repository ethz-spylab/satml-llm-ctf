# prestart.sh

echo "Waiting for Mongo and Redis connection"

while ! nc -z mongo 27017; do
    sleep 0.1
done
echo "Mongo started"

while ! nc -z redis 6379; do
    sleep 0.1
done
echo "Redis started"

exec "$@"