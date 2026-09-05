"""Domain enums.

Values mirror the Postgres enum types created by Prisma exactly — underscore
form, PascalCase type names. The public API speaks hyphenated slugs; convert
with `src.utils.slugs`.
"""

from enum import StrEnum


class ArticleCategory(StrEnum):
    LATEST_JOB = "latest_job"
    ADMIT_CARD = "admit_card"
    RESULT = "result"
    ANSWER_KEY = "answer_key"
    ADMISSION = "admission"
    SYLLABUS = "syllabus"
    SCHOLARSHIP = "scholarship"
    TENDER = "tender"
    SARKARI_WEBSITE = "sarkari_website"
    SARKARI_MOBILE_APP = "sarkari_mobile_app"
    BLOG = "blog"


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class UserRole(StrEnum):
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"


class StateName(StrEnum):
    """Indian states and union territories, as stored by the `StateName` type.

    Unused by this API's own endpoints but present on `User`, so it must be
    mapped with the native enum type — binding it as text makes every INSERT
    fail with a datatype mismatch.
    """

    ANDHRA_PRADESH = "andhra_pradesh"
    ARUNACHAL_PRADESH = "arunachal_pradesh"
    ASSAM = "assam"
    BIHAR = "bihar"
    CHHATTISGARH = "chhattisgarh"
    GOA = "goa"
    GUJARAT = "gujarat"
    HARYANA = "haryana"
    HIMACHAL_PRADESH = "himachal_pradesh"
    JHARKHAND = "jharkhand"
    KARNATAKA = "karnataka"
    KERALA = "kerala"
    MADHYA_PRADESH = "madhya_pradesh"
    MAHARASHTRA = "maharashtra"
    MANIPUR = "manipur"
    MEGHALAYA = "meghalaya"
    MIZORAM = "mizoram"
    NAGALAND = "nagaland"
    ODISHA = "odisha"
    PUNJAB = "punjab"
    RAJASTHAN = "rajasthan"
    SIKKIM = "sikkim"
    TAMIL_NADU = "tamil_nadu"
    TELANGANA = "telangana"
    TRIPURA = "tripura"
    UTTAR_PRADESH = "uttar_pradesh"
    UTTARAKHAND = "uttarakhand"
    WEST_BENGAL = "west_bengal"
    ANDAMAN_AND_NICOBAR_ISLANDS = "andaman_and_nicobar_islands"
    CHANDIGARH = "chandigarh"
    DADRA_AND_NAGAR_HAVELI_AND_DAMAN_AND_DIU = (
        "dadra_and_nagar_haveli_and_daman_and_diu"
    )
    DELHI = "delhi"
    JAMMU_AND_KASHMIR = "jammu_and_kashmir"
    LADAKH = "ladakh"
    LAKSHADWEEP = "lakshadweep"
    PUDUCHERRY = "puducherry"
