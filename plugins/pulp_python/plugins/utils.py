import re


def sanitize_name(name):
    """
    Strips out all non-alphanumeric characters, including underscores, and replaces them with
    hyphens. Runs of multiple non-alphanumeric characters are replaced by only one hyphen.
    This is to take a given python package name and create an iteration of it that can be
    used as part of a url, e.g. for the simple api.
    :param name:  A project name to sanitize
    :type  name:  str
    :return:    The sanitized project name
    :rtype:     str
    """
    return re.sub('[^A-Za-z0-9]+', '-', name).lower()
