from django.core.management.base import BaseCommand

from routing.services.stations_build import build


class Command(BaseCommand):
    help = "Geocode the raw fuel-price CSV to city centroids and write routing/data/stations.csv"

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS(f"Built stations.csv: {build()}"))
