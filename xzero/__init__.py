__version__ = '0.0.1'

import json
from xone import utils, files


def show_value(value, digit=1):
    """
    Use thousand seperator to display values
    """
    return utils.format_float(digit=digit)(value)


def show_qty(value):
    """
    Use thousand seperator to display quantities
    """
    return utils.format_float(digit=0)(value)


class ZeroBase(object):
    """
    Base class for this platform

    Provides some basic functionalities for all sub-classes
    """
    _preserved_ = ['info']

    def __init__(self, **kwargs): pass

    def __repr__(self):
        """
        String representation of class with __dict__ members
        Private members will be ignored

        Returns:
            str
        """
        return f'{self.__class__.__name__}({utils.to_str(self.to_dict())[1:-1]})'

    @classmethod
    def from_dict(cls, **info_dict):
        """
        Instantiate class from dict

        Args:
            **info_dict: kwargs to create class instance

        Returns:
            Class instance
        """
        return cls(**info_dict)

    @classmethod
    def from_json(cls, json_file):
        """
        Instantiate class from json file

        Args:
            json_file: json file path

        Returns:
            Class instance
        """
        if not files.exists(json_file): raise FileExistsError(
            f'{json_file} not exists to initiate {cls.__class__.__name__}'
        )
        with open(json_file, 'r') as fp: return cls(**json.load(fp=fp))

    def to_dict(self):
        """
        Convert class instance to dict

        Returns:
            dict

        Examples:
            >>> t = ZeroBase.from_dict()
            >>> assert str(t) == 'ZeroBase()'
        """
        cls_info = {
            k: v for k, v in self.__dict__.items()
            if (k not in self._preserved_) and (k[0] != '_')
        }
        for pre in self._preserved_:
            if pre in self.__dict__: cls_info.update(self.__dict__[pre])

        return cls_info

    def to_json(self, json_file):
        """
        Save class instance to json file

        Args:
            json_file: json file path
        """
        files.create_folder(json_file, is_file=True)
        with open(json_file, 'w') as fp:
            json.dump(self.to_dict(), fp=fp, indent=2, default=str)


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
