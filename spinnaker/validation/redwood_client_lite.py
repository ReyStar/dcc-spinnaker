import requests

# A lightweight client that calls a redwood server API
# to download small files or parts of larger files.

# Two kinds of downloading :
# download an entire json file and return the contents as json
# download a partial file of any type and return the bytes


# Downloads an entire object and returns it as json
# redwood_storage_url : eg https://storage2.ucsc-cgl.org:5431
# object_id : uuid of the object
# redwood_key : key for the redwood storage server (not an AWS key)
def download_json(redwood_storage_url, object_id, redwood_key):
    aws_url = get_aws_url(redwood_storage_url, object_id, redwood_key)
    aws_response = requests.get(aws_url)
    return aws_response.json()


# Talk to the redwood server and get an aws signed URL for the passed-in object_id
# raises RedwoodServerError if a an error response is received from the server
def get_aws_url(redwood_storage_url, object_id, redwood_key):
    parameters = {'offset': '0', 'length': '-1', 'external': 'true'}
    url = '%s/download/%s' % (redwood_storage_url, object_id)
    header = {'AUTHORIZATION': 'Bearer %s' % redwood_key}
    # TODO  specify a timeout to prevent server from potentially hanging forever in prod mode
    try:
        result = requests.get(url, headers=header, params=parameters).json()
    except requests.exceptions.ConnectionError as error:
        raise RedwoodServerError(error)
    try:
        aws_url = result['parts'][0]['url']
    except KeyError:
        raise RedwoodServerError(result)
    return aws_url


# Download the first range_len bytes of the requested object and return the content
def download_partial_file(redwood_storage_url, object_id, redwood_key, range_len="64"):
    aws_url = get_aws_url(redwood_storage_url, object_id, redwood_key)
    header = {'Range': range_len}
    aws_response = requests.get(aws_url, headers=header)
    return aws_response.content


class RedwoodServerError(Exception):
    """Exception due to a problem interacting with the Redwood Server."""
    pass


# Standalone: Just return the URL.
def main(*args):
    print get_aws_url(*args)


if __name__ == "__main__":
    main()
