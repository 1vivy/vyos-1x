# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.


def colon_separated_to_dict(data_string, uniquekeys=False):
    """ Converts a string containing newline-separated entries
        of colon-separated key-value pairs into a dict.

        Such files are common in Linux /proc filesystem

    Args:
        data_string (str): data string
        uniquekeys (bool): whether to insist that keys are unique or not

    Returns: dict

    Raises:
        ValueError: if uniquekeys=True and the data string has
            duplicate keys.

    Note:
        If uniquekeys=True, then dict entries are always strings,
        otherwise they are always lists of strings.
    """
    import re
    key_value_re = re.compile('([^:]+)\s*\:\s*(.*)')

    data_raw = re.split('\n', data_string)

    data = {}

    for l in data_raw:
        l = l.strip()
        if l:
            match = re.match(key_value_re, l)
            if match and (len(match.groups()) == 2):
                key = match.groups()[0].strip()
                value = match.groups()[1].strip()
            else:
                raise ValueError(f"""Line "{l}" could not be parsed a colon-separated pair """, l)
            if key in data.keys():
                if uniquekeys:
                    raise ValueError("Data string has duplicate keys: {0}".format(key))
                else:
                    data[key].append(value)
            else:
                if uniquekeys:
                    data[key] = value
                else:
                    data[key] = [value]
        else:
            pass

    return data

def _mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False, mod=0):
    """ Mangles dict keys according to a regex and replacement character.
    Some libraries like Jinja2 do not like certain characters in dict keys.
    This function can be used for replacing all offending characters
    with something acceptable.

    Args:
        data (dict): Original dict to mangle

    Returns: dict
    """
    from vyos.xml import is_tag

    new_dict = {}

    for key in data.keys():
        save_mod = mod
        save_path = abs_path[:]

        abs_path.append(key)

        if not is_tag(abs_path):
            new_key = re.sub(regex, replacement, key)
        else:
            if mod%2:
                new_key = key
            else:
                new_key = re.sub(regex, replacement, key)
            if no_tag_node_value_mangle:
                mod += 1

        value = data[key]

        if isinstance(value, dict):
            new_dict[new_key] = _mangle_dict_keys(value, regex, replacement, abs_path=abs_path, mod=mod, no_tag_node_value_mangle=no_tag_node_value_mangle)
        else:
            new_dict[new_key] = value

        mod = save_mod
        abs_path = save_path[:]

    return new_dict

def mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False):
    return _mangle_dict_keys(data, regex, replacement, abs_path=abs_path, no_tag_node_value_mangle=no_tag_node_value_mangle, mod=0)

def _get_sub_dict(d, lpath):
    k = lpath[0]
    if k not in d.keys():
        return {}
    c = {k: d[k]}
    lpath = lpath[1:]
    if not lpath:
        return c
    elif not isinstance(c[k], dict):
        return {}
    return _get_sub_dict(c[k], lpath)

def get_sub_dict(source, lpath, get_first_key=False):
    """ Returns the sub-dict of a nested dict, defined by path of keys.

    Args:
        source (dict): Source dict to extract from
        lpath (list[str]): sequence of keys

    Returns: source, if lpath is empty, else
             {key : source[..]..[key]} for key the last element of lpath, if exists
             {} otherwise
    """
    if not isinstance(source, dict):
        raise TypeError("source must be of type dict")
    if not isinstance(lpath, list):
        raise TypeError("path must be of type list")
    if not lpath:
        return source

    ret =  _get_sub_dict(source, lpath)

    if get_first_key and lpath and ret:
        tmp = next(iter(ret.values()))
        if not isinstance(tmp, dict):
            raise TypeError("Data under node is not of type dict")
        ret = tmp

    return ret

def dict_search(path, dict_object):
    """ Traverse Python dictionary (dict_object) delimited by dot (.).
    Return value of key if found, None otherwise.

    This is faster implementation then jmespath.search('foo.bar', dict_object)"""
    if not isinstance(dict_object, dict) or not path:
        return None

    parts = path.split('.')
    inside = parts[:-1]
    if not inside:
        if path not in dict_object:
            return None
        return dict_object[path]
    c = dict_object
    for p in parts[:-1]:
        c = c.get(p, {})
    return c.get(parts[-1], None)

def dict_search_args(dict_object, *path):
    # Traverse dictionary using variable arguments
    # Added due to above function not allowing for '.' in the key names
    # Example: dict_search_args(some_dict, 'key', 'subkey', 'subsubkey', ...)
    if not isinstance(dict_object, dict) or not path:
        return None

    for item in path:
        if item not in dict_object:
            return None
        dict_object = dict_object[item]
    return dict_object

def dict_search_recursive(dict_object, key, path=[]):
    """ Traverse a dictionary recurisvely and return the value of the key
    we are looking for.

    Thankfully copied from https://stackoverflow.com/a/19871956

    Modified to yield optional path to found keys
    """
    if isinstance(dict_object, list):
        for i in dict_object:
            new_path = path + [i]
            for x in dict_search_recursive(i, key, new_path):
                yield x
    elif isinstance(dict_object, dict):
        if key in dict_object:
            new_path = path + [key]
            yield dict_object[key], new_path
        for k, j in dict_object.items():
            new_path = path + [k]
            for x in dict_search_recursive(j, key, new_path):
                yield x

def dict_to_list(d, save_key_to=None):
    """ Convert a dict to a list of dicts.

    Optionally, save the original key of the dict inside
    dicts stores in that list.
    """
    def save_key(i, k):
        if isinstance(i, dict):
            i[save_key_to] = k
            return
        elif isinstance(i, list):
            for _i in i:
                save_key(_i, k)
        else:
            raise ValueError(f"Cannot save the key: the item is {type(i)}, not a dict")

    collect = []

    for k,_ in d.items():
        item = d[k]
        if save_key_to is not None:
            save_key(item, k)
        if isinstance(item, list):
            collect += item
        else:
            collect.append(item)

    return collect

def check_mutually_exclusive_options(d, keys, required=False):
    """ Checks if a dict has at most one or only one of
    mutually exclusive keys.
    """
    present_keys = []

    for k in d:
        if k in keys:
            present_keys.append(k)

    # Un-mangle the keys to make them match CLI option syntax
    from re import sub
    orig_keys = list(map(lambda s: sub(r'_', '-', s), keys))
    orig_present_keys = list(map(lambda s: sub(r'_', '-', s), present_keys))

    if len(present_keys) > 1:
        raise ValueError(f"Options {orig_keys} are mutually-exclusive but more than one of them is present: {orig_present_keys}")

    if required and (len(present_keys) < 1):
        raise ValueError(f"At least one of the following options is required: {orig_present_keys}")
