# Copyright (c) 2020 jya
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Library-specific exception classes."""

class SupernoteLibException(Exception):
    """Base class of all Supernote library exceptions."""

class ParserException(SupernoteLibException):
    """Base class of parser exceptions."""

class UnsupportedFileFormat(ParserException):
    """Raised if file format is unsupported."""

class DecoderException(SupernoteLibException):
    """Base class of decoder exceptions."""

class UnknownDecodeProtocol(DecoderException):
    """Raised if decode protocol is unknown."""
