from datetime import datetime

from discord import Embed

from kekmonitors import shoe_stuff
from kekmonitors.config import Config
from kekmonitors.shoe_stuff import Shoe


def get_empty_embed() -> Embed:
    """Get an almost empty embed (only set color and timestamp)"""
    empty_embed = Embed()
    empty_embed.timestamp = datetime.utcnow()
    return empty_embed


def add_link(s: str, link: str) -> str:
    """Add a link to the string s in markdown format"""
    return "[" + s + "](" + link + ")"


def get_scraper_embed(shoe: Shoe, friendly_website_name=""):
    embed = get_empty_embed()

    embed.title = "New item scraped"
    if friendly_website_name:
        embed.title += " on " + friendly_website_name
    if shoe.name:
        embed.title += f": {shoe.name}"
    embed.url = shoe.link

    if shoe.img_link:
        embed.set_thumbnail(url=shoe.img_link)

    if shoe.price != "Not available":
        embed.add_field(name="Price", value=shoe.price, inline=False)

    return embed


def get_mm_crash_embed(what: str, code: int, pid: int) -> Embed:
    embed = get_empty_embed()
    embed.title = "MonitorManager: something has crashed!"
    embed.add_field(name="What: ", value=what, inline=True)
    embed.add_field(name="PID: ", value=pid, inline=True)
    embed.add_field(name="Exit code:  ", value=str(code), inline=True)
    embed.timestamp = Embed.Empty
    return embed


def get_default_embed(shoe: Shoe, allow_unavailable_sizes=False, show_website=False):
    """Do you really need help to understand this?"""
    embed = get_empty_embed()

    embed.title = shoe.name
    embed.url = shoe.link
    embed.set_thumbnail(url=shoe.img_link)

    if show_website:
        if not isinstance(embed.description, str):
            embed.description = ""
        embed.description += (
            "\n" + shoe.link[shoe.link.find("/") + 2 : shoe.link.find("/", 8)]
        )

    if shoe.reason == shoe_stuff.NEW_RELEASE:
        embed.add_field(name="Notification type", value="New item", inline=False)
    if shoe.reason == shoe_stuff.RESTOCK:
        embed.add_field(name="Notification type", value="Restock", inline=False)

    if shoe.price != "Not available":
        embed.add_field(name="Price", value=shoe.price, inline=False)

    if shoe.release_date != "":
        if shoe.release_method != "":
            embed.add_field(name="Release date", value=shoe.release_date)
            embed.add_field(name="Release method", value=shoe.release_method)
        else:
            embed.add_field(name="Release date", value=shoe.release_date)

    # Add sizes to the embed
    sizes = []
    total_chars = 0
    for size in shoe.sizes:
        available = shoe.sizes[size]["available"]
        # Only add sizes under these conditions
        if available or (not available and allow_unavailable_sizes):
            size_str = size
            # Add the stock number if available
            if "stock" in shoe.sizes[size]:
                size_str += " (" + str(shoe.sizes[size]["stock"]) + ")"
            # Add atc if available
            if "atc" in shoe.sizes[size] and shoe.sizes[size]["atc"] != "":
                atc = shoe.sizes[size]["atc"]
                atc_str = add_link("[ATC]", atc)
                size_str += " - " + atc_str
            # Add quick tasks if available
            if "quick_tasks" in shoe.sizes[size]:
                qts = []
                for key, value in zip(
                    shoe.sizes[size]["quick_tasks"].keys(),
                    shoe.sizes[size]["quick_tasks"].values(),
                ):
                    qts.append(add_link(key, value))
                qts_str = " - ".join(qts)
                size_str += " - " + qts_str
            # Add anything else
            if "other" in shoe.sizes[size]:
                others_list = []
                for other in shoe.sizes[size]["other"]:
                    other_str = ""
                    if "link" in other:
                        other_str = add_link(other["name"], other["link"])
                    else:
                        other_str = other["name"]
                    others_list.append(other_str)
                others_str = " - ".join(others_list)
                size_str += " - " + others_str
            sizes.append(size_str)
            total_chars += len(size_str)

    # get well formatted sizes.
    values = get_valid_values(sizes, 6)

    for index, value in enumerate(values):
        if index == 0:
            inline = True if len(values) > 0 else False
            embed.add_field(name="Sizes", value=value, inline=inline)
        else:
            embed.add_field(name="\u200b", value=value, inline=True)

    return embed


def get_valid_values(values_list, max_elements):
    """This function tries to format a list splitting it in max_elements and keeping count of discord's max chars limit.\n
    See comments for more insight."""
    if len(values_list) == 0:
        return []
    # not perfect. if many small values and very close to 1023 chars it might truncate the lasts of them.
    # also, this requires too much fucking math.
    tmp = ""
    done = False
    valid_values = []
    count = 0
    for value in values_list:
        done = False
        if len(tmp) + len("\n") + len(value) > 1023 or (
            count != 0 and count % max_elements == 0
        ):
            if tmp == "":
                # first cycle / 1 item
                tmp = value
            done = True
            valid_values.append(tmp)
            tmp = ""
            count = 0
        tmp += value + "\n"
        count += 1
    if not done:
        valid_values.append(tmp)
    return valid_values


def website_specific_embed(shoe: Shoe) -> Embed:
    """What a website-specific embed function might look like."""
    fd_embed = get_default_embed(shoe)
    if shoe.reason == shoe_stuff.NEW_RELEASE:
        if shoe.sizes == {}:
            fd_embed.add_field(
                name="Info",
                value="If sizes are not displayed check manually!",
                inline=False,
            )
    if "alternative_url" in shoe.other:
        fd_embed.description = (
            f"\n\n[Alternative link]({shoe.other['alternative_url']})"
        )
    return fd_embed
