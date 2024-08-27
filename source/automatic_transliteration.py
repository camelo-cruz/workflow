# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz, Arne Goelz

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
        
Leibniz Institute General Linguistics (ZAS)
"""

if language == "ru":
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'ru',reversed=True)}"
elif language == "uk":
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'uk',reversed=True)}"
elif language == "ja":
    katsu = cutlet.Cutlet()
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {katsu.romaji(transcription)}"