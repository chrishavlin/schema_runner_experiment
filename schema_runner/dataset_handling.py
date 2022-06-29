import contextlib
import yt
from pathlib import PosixPath


class DatasetContext:
    def __init__(self, fn, *args, **kwargs):
        self.filename = fn
        self.load_args = args
        self.load_kwargs = kwargs

    @contextlib.contextmanager
    def load(self):
        print(f"\n\nloading {self.filename}\n\n")
        ds = yt.load(self.filename, *self.load_args, **self.load_kwargs)
        try:
            yield ds
        finally:
            # ds.close doesnt do anything for majority of frontends... might
            # as well call it though.
            ds.close()

    @contextlib.contextmanager
    def load_sample(self):
        print(f"\n\nloading {self.filename}\n\n")
        ds = yt.load_sample(self.filename, *self.load_args, **self.load_kwargs)
        try:
            yield ds
        finally:
            # ds.close doesnt do anything for majority of frontends... might
            # as well call it though.
            ds.close()


# a version of DatasetFixture
class DataStore:
    """
    A class to hold all dataset references.
    """

    def __init__(self):
        self.all_data = {}

    def store(self, fn: str, dataset_name: str = None, load_method='load'):
        """
        A function to track all dataset.
        Stores dataset name, or if no name is provided,
        adds a number as the name.
        """
        dataset_name = self.validate_name(fn, dataset_name)

        if dataset_name not in self.all_data:
            self.all_data[dataset_name] = DatasetContext(fn, load_method=load_method)

    def validate_name(self, fn: str, dataset_name: str = None):
        if dataset_name is None:
            if isinstance(fn, PosixPath):
                fn = str(fn)
            dataset_name = fn
        return dataset_name

    def retrieve(
        self,
        dataset_name: str,
    ):
        """
        Instantiates a dataset and stores it in a separate dictionary.
        Returns a dataset context
        """
        if dataset_name in self.all_data:
            return self.all_data[dataset_name]
        else:
            raise KeyError(f"{dataset_name} is not in the DataStore")

    def list_available(self):
        return list(self.all_data.keys())






