import sys
import json

from lf_toolkit.shared.params import Params

from .evaluation import evaluation_function

def dev():
    """Run the evaluation function from the command line for development purposes.

    Usage: python -m evaluation_function.dev <response> <answer> [params_json]

    `params_json` is an optional JSON object passed through as Params, e.g.
        '{"direction": "ipa_to_word"}'
        '{"accents": ["en_US"]}'
    """
    if len(sys.argv) < 3:
        print("Usage: python -m evaluation_function.dev <response> <answer> [params_json]")
        return

    response = sys.argv[1]
    answer = sys.argv[2]

    params = Params()
    if len(sys.argv) > 3:
        params = Params(**json.loads(sys.argv[3]))

    result = evaluation_function(response, answer, params)

    print(result.to_dict())

if __name__ == "__main__":
    dev()
