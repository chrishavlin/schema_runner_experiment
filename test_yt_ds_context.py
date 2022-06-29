from schema_runner.dataset_handling import DatasetContext


dc = DatasetContext("IsolatedGalaxy")

with dc.load_sample() as ds:
    ad = ds.all_data()
    extrema = ad.quantities.extrema(("gas", "density"))
