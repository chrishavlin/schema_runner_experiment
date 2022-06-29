import abc
import analysis_schema
import yt
import inspect


class YTRunner(abc.ABC):

    @abc.abstractmethod
    def process_pydantic(self, pydantic_instance, ds=None):
        # take the pydantic model and return another object
        pass

    def run(self, pydantic_instance, ds = None):
        return self.process_pydantic(pydantic_instance, ds=ds)


class FieldNames(YTRunner):
    def process_pydantic(self, pydantic_instance: analysis_schema.data_classes.FieldNames, ds=None):
        return (pydantic_instance.field_type, pydantic_instance.field)


class Dataset(YTRunner):
    def process_pydantic(self, pydantic_instance: analysis_schema.data_classes.Dataset, ds=None):
        # always return the instantiated dataset
        return ds


class DataSource3D(YTRunner):
    def process_pydantic(self, pydantic_instance: analysis_schema.data_classes.DataSource3D, ds=None):
        for pyfield in pydantic_instance.__fields__.keys():
            pyval = getattr(pydantic_instance, pyfield, None)
            if pyval is not None:
                runner = YTGeneric()
                return runner.run(pyval, ds=ds)
        return None


class YTGeneric(YTRunner):
    @staticmethod
    def _determine_callable(pydantic_instance, ds=None):
        if hasattr(pydantic_instance, "_yt_operation"):
            yt_op = pydantic_instance._yt_operation  # e.g., SlicePlot, sphere
        else:
            yt_op = type(pydantic_instance).__name__

        if hasattr(yt, yt_op):  # check top api
            return getattr(yt, yt_op)
        elif hasattr(ds, yt_op):  # check ds-level api
            return getattr(ds, yt_op)

        raise RuntimeError("could not determine yt callable")

    def _check_and_run(self, value, ds=None):
        # potentially recursive as well
        if _is_yt_schema_instance(value):
            runner = yt_registry.get(value)
            return runner.run(value, ds=ds)
        elif isinstance(value, list):
            if len(value) and _is_yt_schema_instance(value[0]):
                if isinstance(value[0], analysis_schema.data_classes.Dataset):
                    return self._check_and_run(value[0], ds=ds)
                return [self._check_and_run(val, ds=ds) for val in value]
            return value
        else:
            return value

    def process_pydantic(self, pydantic_instance, ds=None):
        yt_func = self._determine_callable(pydantic_instance, ds=ds)
        # the list that we'll use to eventually call our function
        the_args = []

        # now we get the arguments for the function:
        # func_spec.args, which lists the named arguments and keyword arguments.
        # ignoring vargs and kw-only args for now...
        # see https://docs.python.org/3/library/inspect.html#inspect.getfullargspec
        func_spec = inspect.getfullargspec(yt_func)

        # the argument position number at which we have default values (a little
        # hacky, should be a better way to do this, and not sure how to scale it to
        # include *args and **kwargs)
        n_args = len(func_spec.args)  # number of arguments
        if func_spec.defaults is None:
            # no default args, make sure we never get there...
            named_kw_start_at = n_args + 1
        else:
            # the position at which named keyword args start
            named_kw_start_at = n_args - len(func_spec.defaults)

        # loop over the call signature arguments and pull out values from our pydantic
        # class. this is recursive! will call _run() if a given argument value is also
        # a ytBaseModel.
        for arg_i, arg in enumerate(func_spec.args):
            if arg in ["self", "cls"]:
                continue

            # get the value for this argument. If it's not there, attempt to set default
            # values for arguments needed for yt but not exposed in our pydantic class
            try:
                arg_value = getattr(pydantic_instance, arg)
                if arg_value is None:
                    default_index = arg_i - named_kw_start_at
                    arg_value = func_spec.defaults[default_index]
            except AttributeError:
                if arg_i >= named_kw_start_at:
                    # we are in the named keyword arguments, grab the default
                    # the func_spec.defaults tuple 0 index is the first named
                    # argument, so need to offset the arg_i counter
                    default_index = arg_i - named_kw_start_at
                    arg_value = func_spec.defaults[default_index]
                else:
                    raise AttributeError(f"could not file {arg}")

            arg_value = self._check_and_run(arg_value, ds=ds)
            the_args.append(arg_value)

        # if this class has a list of known kwargs that we know will not be
        # picked up by argspec, add them here. Not using inspect here because
        # some of the yt visualization classes pass along kwargs, so we need
        # to do this semi-manually for some classes and functions.
        kwarg_dict = {}
        if getattr(pydantic_instance, "_known_kwargs", None):
            for kw in pydantic_instance._known_kwargs:
                arg_value = getattr(pydantic_instance, kw, None)
                arg_value = self._check_and_run(arg_value, ds=ds)
                kwarg_dict[kw] = arg_value

        return yt_func(*the_args, **kwarg_dict)


class Visualizations(YTRunner):

    def _sanitize_viz(self, yt_viz):
        # if objects contain references to a ds, that might be problematic when
        # loading and executing a single ds at a time?
        return yt_viz

    def process_pydantic(self, pydantic_instance: analysis_schema.data_classes.Visualizations, ds=None):
        generic_runner = YTGeneric()
        viz_results = {}
        for attr in pydantic_instance.__fields__.keys():
            viz_model = getattr(pydantic_instance, attr)  # SlicePlot, etc.
            if viz_model is not None:
                result = generic_runner.run(viz_model, ds=ds)
                nme = f"{ds.basename}_{attr}"
                viz_results[nme] = self._sanitize_viz(result)
        return viz_results


class RunnerRegistry:

    def __init__(self):
        self._registry = {}

    def register(self, pydantic_class, runner):
        if isinstance(runner, YTRunner) is False:
            raise ValueError("the runner must be a YTRunner instance")
        self._registry[pydantic_class] = runner

    def get(self, pydantic_class_instance):
        pyd_type = type(pydantic_class_instance)
        if pyd_type in self._registry:
            return self._registry[pyd_type]
        return YTGeneric()


def _is_yt_schema_instance(obj):
    is_model = isinstance(obj, analysis_schema.base_model.ytBaseModel)
    is_param = isinstance(obj, analysis_schema.base_model.ytParameter)
    is_viz = isinstance(obj, analysis_schema.data_classes.Visualizations)
    return is_param or is_model or is_viz


yt_registry = RunnerRegistry()
yt_registry.register(analysis_schema.data_classes.FieldNames, FieldNames())
yt_registry.register(analysis_schema.data_classes.Visualizations, Visualizations())
yt_registry.register(analysis_schema.data_classes.Dataset, Dataset())
yt_registry.register(analysis_schema.data_classes.DataSource3D, DataSource3D())
