import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from utils import get_all_types, get_non_type

from kekmonitors.exceptions import MissingRequired
from kekmonitors.shoe_stuff import *


@pytest.fixture
def shoe():
    return Shoe()


def test_shoe_name(shoe):
    names = ["", "123", "test123"]
    for name in names:
        shoe.name = name
        assert shoe.name == name

    names = get_non_type(str)
    for name in names:
        with pytest.raises(TypeError):
            shoe.name = name


def test_shoe_link(shoe):
    links = ["", "123", "test123"]
    for link in links:
        shoe.link = link
        assert shoe.link == link

    links = get_non_type(str)
    for link in links:
        with pytest.raises(TypeError):
            shoe.link = link


def test_shoe_img_link(shoe):
    img_links = ["", "123", "test123"]
    for img_link in img_links:
        shoe.img_link = img_link
        assert shoe.img_link == img_link

    img_links = get_non_type(str)
    for img_link in img_links:
        with pytest.raises(TypeError):
            shoe.img_link = img_link


def test_shoe_price(shoe):
    prices = ["", "123", "test123"]
    for price in prices:
        shoe.price = price
        assert shoe.price == price

    prices = get_non_type(str)
    for price in prices:
        with pytest.raises(TypeError):
            shoe.price = price


def test_shoe_style_code(shoe):
    style_codes = ["", "123", "test123"]
    for style_code in style_codes:
        shoe.style_code = style_code
        assert shoe.style_code == style_code

    style_codes = get_non_type(str)
    for style_code in style_codes:
        with pytest.raises(TypeError):
            shoe.style_code = style_code


def test_shoe_release_date(shoe):
    release_dates = ["", "123", "test123"]
    for release_date in release_dates:
        shoe.release_date = release_date
        assert shoe.release_date == release_date

    release_dates = get_non_type(str)
    for release_date in release_dates:
        with pytest.raises(TypeError):
            shoe.release_date = release_date


def test_shoe_release_method(shoe):
    release_methods = ["", "123", "test123"]
    for release_method in release_methods:
        shoe.release_method = release_method
        assert shoe.release_method == release_method

    release_methods = get_non_type(str)
    for release_method in release_methods:
        with pytest.raises(TypeError):
            shoe.release_method = release_method


def test_shoe_in_stock(shoe):
    in_stocks = [True, False]
    for in_stock in in_stocks:
        shoe.in_stock = in_stock
        assert shoe.in_stock == in_stock

    in_stocks = get_non_type(bool)
    for in_stock in in_stocks:
        with pytest.raises(TypeError):
            shoe.in_stock = in_stock


def test_shoe_out_of_stock(shoe):
    out_of_stocks = [True, False]
    for out_of_stock in out_of_stocks:
        shoe.out_of_stock = out_of_stock
        assert shoe.out_of_stock == out_of_stock

    out_of_stocks = get_non_type(bool)
    for out_of_stock in out_of_stocks:
        with pytest.raises(TypeError):
            shoe.out_of_stock = out_of_stock


def test_shoe_back_in_stock(shoe):
    back_in_stocks = [True, False]
    for back_in_stock in back_in_stocks:
        shoe.back_in_stock = back_in_stock
        assert shoe.back_in_stock == back_in_stock

    back_in_stocks = get_non_type(bool)
    for back_in_stock in back_in_stocks:
        with pytest.raises(TypeError):
            shoe.back_in_stock = back_in_stock


def test_shoe_reason(shoe):
    for reason in (OTHER, INCOMING, NEW_RELEASE, RESTOCK):
        shoe.reason = reason
        assert shoe.reason == reason

    for wrong_reason in get_non_type(int):
        with pytest.raises(TypeError):
            shoe.reason = wrong_reason

    with pytest.raises(ValueError):
        shoe.reason = -1


def test_shoe_sizes(shoe):
    # assert shoe.sizes only accepts dict
    sizess = get_non_type(dict)
    for sizes in sizess:
        with pytest.raises(TypeError):
            shoe.sizes = sizes

    # assert shoe.sizes only accepts str as key, shoe.sizes[size] only accepts dict
    types = get_all_types()
    for size in types:
        for size_val in types:
            if not isinstance(size, str):
                with pytest.raises(TypeError):
                    shoe.sizes = {size: size_val}
            if not isinstance(size_val, dict):
                with pytest.raises(TypeError):
                    shoe.sizes = {size: size_val}

    # assert "available" is needed
    with pytest.raises(MissingRequired):
        shoe.sizes = {"size": {}}
    with pytest.raises(MissingRequired):
        shoe.sizes = {"size": {"key": "value"}}
    for t in get_non_type(bool):
        with pytest.raises(TypeError):
            shoe.sizes = {"size": {"available": t}}
    sizes = {"size": {"available": False}}
    shoe.sizes = sizes
    assert shoe.sizes == sizes

    # assert correct type for keys
    correct_kw = {"atc": str}
    for kw in correct_kw:
        for t in types:
            if not isinstance(t, correct_kw[kw]):
                with pytest.raises(TypeError):
                    shoe.sizes = {"size": {kw: t, "available": False}}
            else:
                sizes = {"size": {kw: t, "available": False}}
                shoe.sizes = sizes
                assert shoe.sizes == sizes
