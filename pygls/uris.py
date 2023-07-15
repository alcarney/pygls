############################################################################
# Original work Copyright 2017 Palantir Technologies, Inc.                 #
# Original work licensed under the MIT License.                            #
# See ThirdPartyNotices.txt in the project root for license information.   #
# All modifications Copyright (c) Open Law Library. All rights reserved.   #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License")           #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#     http: // www.apache.org/licenses/LICENSE-2.0                         #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
############################################################################
"""A collection of URI utilities with logic built on the VSCode URI library.

https://github.com/Microsoft/vscode-uri/blob/e59cab84f5df6265aed18ae5f43552d3eef13bb9/lib/index.ts
"""
import os.path
import re
from typing import Optional
from urllib import parse

import attrs

from pygls import IS_WIN

SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z\d+.-]*$")
RE_DRIVE_LETTER_PATH = re.compile(r"^(\/?)([a-zA-Z]:)")


@attrs.define(frozen=True)
class Uri:
    scheme: str

    authority: str

    path: str

    query: str

    fragment: str

    def __attrs_post_init__(self):
        """Basic validation."""
        if self.scheme is None:
            raise ValueError("URIs must have a scheme")

        if not SCHEME.match(self.scheme):
            raise ValueError("Invalid scheme")

        if self.authority and self.path and (not self.path.startswith("/")):
            raise ValueError("Paths with an authority must start with a slash '/'")

        if self.path and self.path.startswith("//") and (not self.authority):
            raise ValueError(
                "Paths without an authority cannot start with two slashes '//'"
            )

    def __fspath__(self):
        """Return the file system representation of this uri.

        This makes Uri instances compatible with any function that expects an
        ``os.PathLike`` object!
        """
        # TODO: Should we raise an exception if scheme != "file"?
        return self.fs_path

    def __str__(self):
        return self.as_string()

    def __truediv__(self, other):
        return self.join(other)

    @classmethod
    def create(
        cls,
        *,
        scheme: str = "",
        authority: str = "",
        path: str = "",
        query: str = "",
        fragment: str = "",
    ) -> "Uri":
        """Create a uri with the given attributes."""

        if scheme in {"http", "https", "file"}:
            if not path.startswith("/"):
                path = f"/{path}"

        return cls(
            scheme=scheme,
            authority=authority,
            path=path,
            query=query,
            fragment=fragment,
        )

    @classmethod
    def parse(cls, uri: str) -> "Uri":
        """Parse the given uri from its string representation."""
        scheme, authority, path, _, query, fragment = urlparse(uri)
        return cls.create(
            scheme=scheme,
            authority=authority,
            path=path,
            query=query,
            fragment=fragment,
        )

    @classmethod
    def for_file(cls, filepath: str) -> "Uri":
        """Create a uri based on the given filepath."""

        if IS_WIN:
            filepath = filepath.replace("\\", "/")

        if filepath.startswith("//"):
            authority, *path = filepath[2:].split("/")
            filepath = "/".join(path)
        else:
            authority = ""

        return Uri.create(scheme="file", authority=authority, path=filepath)

    @property
    def fs_path(self) -> Optional[str]:
        """Return the equivalent fs path."""
        if self.path:
            path = _normalize_path(self.path)

            if self.authority and len(path) > 1:
                path = f"//{self.authority}{path}"

            # Remove the leading `/` from windows paths
            elif RE_DRIVE_LETTER_PATH.match(path):
                path = path[1:]

            if IS_WIN:
                path = path.replace("\\", "/")

            return path

    def where(self, **kwargs) -> "Uri":
        """Return an transformed version of this uri where certain components of the uri
        have been replace with the given arguments.

        Passing a value of ``None`` will remove the given component entirely.
        """
        keys = {"scheme", "authority", "path", "query", "fragment"}
        valid_keys = keys.copy() & kwargs.keys()

        current = {k: getattr(self, k) for k in keys}
        replacements = {k: kwargs[k] for k in valid_keys}

        return Uri.create(**{**current, **replacements})

    def join(self, path: str) -> "Uri":
        """Join this Uri's path component with the given path and return the resulting
        uri.

        Parameters
        ----------
        path
           The path segment to join

        Returns
        -------
        Uri
           The resulting uri
        """

        if not self.path:
            raise ValueError("This uri has no path")

        new_path = os.path.normpath(os.path.join(self.path, path))
        return self.where(path=new_path)

    def as_string(self, encode=True) -> str:
        """Return a string representation of this Uri.

        Parameters
        ----------
        encode
           If ``True`` (the default), encode any special characters.

        Returns
        -------
        str
           The string representation of the Uri
        """

        encoder = parse.quote if encode else _replace_chars

        if authority := self.authority:
            usercred, *auth = authority.split("@")
            if len(auth) > 0:
                *user, cred = usercred.split(":")
                if len(user) > 0:
                    usercred = encoder(":".join(user)) + f":{encoder(cred)}"
                else:
                    usercred = encoder(usercred)
                authority = "@".join(auth)
            else:
                usercred = None

            authority = authority.lower()
            *auth, port = authority.split(":")
            if len(auth) > 0:
                authority = encoder(":".join(auth)) + f":{port}"
            else:
                authority = encoder(authority)

            if usercred:
                authority = f"{usercred}@{authority}"

        scheme_separator = ""
        if authority or self.scheme == "file":
            scheme_separator = "//"

        if path := self.path:
            path = encoder(_normalize_path(path))

        if query := self.query:
            query = encoder(query)

        if fragment := self.fragment:
            fragment = encoder(fragment)

        parts = [
            f"{self.scheme}:",
            scheme_separator,
            authority if authority else "",
            path if path else "",
            f"?{query}" if query else "",
            f"#{fragment}" if fragment else "",
        ]
        return "".join(parts)


def _replace_chars(segment: str) -> str:
    """Replace a certain subset of characters in a uri segment"""
    return segment.replace("#", "%23").replace("?", "%3F")


def _normalize_path(path: str) -> str:
    """Normalise the path segment of a Uri."""

    # normalize to fwd-slashes on windows,
    # on other systems bwd-slashes are valid
    # filename character, eg /f\oo/ba\r.txt
    if IS_WIN:
        path = path.replace("\\", "/")

    # Normalize drive paths to lower case
    if match := RE_DRIVE_LETTER_PATH.match(path):
        path = match.group(1) + match.group(2).lower() + path[match.end() :]

    return path


def _normalize_win_path(path):
    netloc = ""

    # normalize to fwd-slashes on windows,
    # on other systems bwd-slashes are valid
    # filename character, eg /f\oo/ba\r.txt
    if IS_WIN:
        path = path.replace("\\", "/")

    # check for authority as used in UNC shares
    # or use the path as given
    if path[:2] == "//":
        idx = path.index("/", 2)
        if idx == -1:
            netloc = path[2:]
        else:
            netloc = path[2:idx]
            path = path[idx:]

    # Ensure that path starts with a slash
    # or that it is at least a slash
    if not path.startswith("/"):
        path = "/" + path

    # Normalize drive paths to lower case
    if RE_DRIVE_LETTER_PATH.match(path):
        path = path[0] + path[1].lower() + path[2:]

    return path, netloc


def from_fs_path(path):
    """Returns a URI for the given filesystem path."""
    try:
        scheme = "file"
        params, query, fragment = "", "", ""
        path, netloc = _normalize_win_path(path)
        return urlunparse((scheme, netloc, path, params, query, fragment))
    except (AttributeError, TypeError):
        return None


def to_fs_path(uri):
    """Returns the filesystem path of the given URI.

    Will handle UNC paths and normalize windows drive letters to lower-case.
    Also uses the platform specific path separator. Will *not* validate the
    path for invalid characters and semantics.
    Will *not* look at the scheme of this URI.
    """
    try:
        # scheme://netloc/path;parameters?query#fragment
        scheme, netloc, path, _params, _query, _fragment = urlparse(uri)

        if netloc and path and scheme == "file":
            # unc path: file://shares/c$/far/boo
            value = f"//{netloc}{path}"

        elif RE_DRIVE_LETTER_PATH.match(path):
            # windows drive letter: file:///C:/far/boo
            value = path[1].lower() + path[2:]

        else:
            # Other path
            value = path

        if IS_WIN:
            value = value.replace("/", "\\")

        return value
    except TypeError:
        return None


def uri_scheme(uri):
    try:
        return urlparse(uri)[0]
    except (TypeError, IndexError):
        return None


def uri_with(
    uri, scheme=None, netloc=None, path=None, params=None, query=None, fragment=None
):
    """Return a URI with the given part(s) replaced.

    Parts are decoded / encoded.
    """
    old_scheme, old_netloc, old_path, old_params, old_query, old_fragment = urlparse(
        uri
    )

    path, _netloc = _normalize_win_path(path)
    return urlunparse(
        (
            scheme or old_scheme,
            netloc or old_netloc,
            path or old_path,
            params or old_params,
            query or old_query,
            fragment or old_fragment,
        )
    )


def urlparse(uri):
    """Parse and decode the parts of a URI."""
    scheme, netloc, path, params, query, fragment = parse.urlparse(uri)
    return (
        parse.unquote(scheme),
        parse.unquote(netloc),
        parse.unquote(path),
        parse.unquote(params),
        parse.unquote(query),
        parse.unquote(fragment),
    )


def urlunparse(parts):
    """Unparse and encode parts of a URI."""
    scheme, netloc, path, params, query, fragment = parts

    # Avoid encoding the windows drive letter colon
    if RE_DRIVE_LETTER_PATH.match(path):
        quoted_path = path[:3] + parse.quote(path[3:])
    else:
        quoted_path = parse.quote(path)

    return parse.urlunparse(
        (
            parse.quote(scheme),
            parse.quote(netloc),
            quoted_path,
            parse.quote(params),
            parse.quote(query),
            parse.quote(fragment),
        )
    )
