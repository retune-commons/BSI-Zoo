from scipy import linalg
import pandas as pd
from sklearn.utils import check_random_state
from sklearn.model_selection import ParameterGrid


from bsi_zoo.data_generator import get_data
from bsi_zoo.estimators import gamma_map, iterative_sqrt
from bsi_zoo.metrics import euclidean_distance, mse, emd
from bsi_zoo.config import get_leadfield_path


class Benchmark:
    def __init__(
        self,
        estimator,
        subject,
        metrics=[],
        data_args={},
        data_args_to_benchmark={},
        random_state=None,
    ) -> None:
        self.estimator = estimator
        self.subject = subject
        self.metrics = metrics
        self.data_args = data_args
        self.data_args_to_benchmark = data_args_to_benchmark
        self.random_state = random_state

    def run(self, nruns=2):
        # profile = {}
        rng = check_random_state(self.random_state)
        seeds = rng.randint(low=0, high=2 ** 32, size=nruns)

        results = []

        for solver_args in ParameterGrid(self.data_args_to_benchmark):
            data_args = dict(self.data_args)  # make a copy
            data_args.update(solver_args)

            print("Benchmarking this data...")
            print(data_args)

            for seed in seeds:
                # get data
                y, L, x, cov, _ = get_data(**data_args, seed=seed)

                # estimate x_hat
                if self.data_args["cov_type"] == "diag":
                    whitener = linalg.inv(linalg.sqrtm(cov))
                    L = whitener @ L
                    y = whitener @ y
                    x_hat = self.estimator(L, y, **solver_args)
                else:
                    x_hat = self.estimator(L, y, cov, **solver_args)

                this_results = dict(estimator=self.estimator.__name__)
                for metric in self.metrics:
                    metric_score = metric(
                        x,
                        x_hat,
                        subject=self.subject,
                        orientation_type=self.data_args["orientation_type"],
                        nnz=data_args["nnz"],
                    )
                    this_results[metric.__name__] = metric_score
                this_results.update(data_args)
                this_results.update(solver_args)

            results.append(this_results)

        results = pd.DataFrame(results)
        return results


if __name__ == "__main__":

    subject = "CC120264"
    data_args_I = {
        "n_sensors": 50,
        "n_times": 10,
        "n_sources": 200,
        "n_orient": 3,
        "nnz": 2,
        "cov_type": "diag",
        "path_to_leadfield": get_leadfield_path(subject, type="fixed"),
        "orientation_type": "fixed",
        "alpha": 0.99,
    }

    data_args_II = {
        "n_sensors": 50,
        "n_times": 10,
        "n_sources": 200,
        "n_orient": 3,
        "nnz": 2,
        "cov_type": "full",
        "path_to_leadfield": get_leadfield_path(subject, type="fixed"),
        "orientation_type": "fixed",
        "alpha": 0.99,
    }
    metrics = [euclidean_distance, mse, emd]  # list of metric functions here

    estimators = [
        (iterative_sqrt, data_args_I, {"alpha": [0.9, 0.5, 0.2]}),
        (gamma_map, data_args_II, {"alpha": [0.9, 0.5, 0.2]}),
    ]

    df_results = []
    for estimator, data_args, data_args_to_benchmark in estimators:
        benchmark = Benchmark(
            estimator, subject, metrics, data_args, data_args_to_benchmark
        )
        results = benchmark.run(nruns=2)
        df_results.append(results)

    df_results = pd.concat(df_results, axis=0)

    df_results.to_pickle("bsi_zoo/data/benchmark_data_%s.pkl" % (subject))

    print(results)
