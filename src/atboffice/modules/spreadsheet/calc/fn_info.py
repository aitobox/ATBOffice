"""Metadata catalog for all 519 worksheet functions in Ledger."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    category: str
    args: tuple[str, ...]
    desc: str
    classic: bool = False


ALL_FUNCTIONS_CATALOG: dict[str, FunctionInfo] = {
    "ABS": FunctionInfo(
        name="ABS",
        category="Math & Trig",
        args=("number",),
        desc="Returns the absolute value of a number, a number without its sign.",
        classic=True,
    ),
    "ACCRINT": FunctionInfo(
        name="ACCRINT",
        category="Financial",
        args=(
            "issue",
            "first_interest",
            "settlement",
            "rate",
            "par",
            "frequency",
            "[basis]",
            "[calc_method]",
        ),
        desc="Returns the accrued interest for a security that pays periodic interest.",
        classic=True,
    ),
    "ACCRINTM": FunctionInfo(
        name="ACCRINTM",
        category="Financial",
        args=("issue", "settlement", "rate", "par", "[basis]"),
        desc="Returns the accrued interest for a security that pays interest at maturity.",
        classic=True,
    ),
    "ACOS": FunctionInfo(
        name="ACOS",
        category="Math & Trig",
        args=("number",),
        desc="Returns the arccosine of a number, in radians in the range 0 to Pi.",
        classic=True,
    ),
    "ACOSH": FunctionInfo(
        name="ACOSH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the inverse hyperbolic cosine of a number.",
        classic=True,
    ),
    "ACOT": FunctionInfo(
        name="ACOT",
        category="Math & Trig",
        args=("number",),
        desc="Returns the arccotangent of a number, in radians in the range 0 to Pi.",
        classic=False,
    ),
    "ACOTH": FunctionInfo(
        name="ACOTH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the inverse hyperbolic cotangent of a number.",
        classic=False,
    ),
    "ADDRESS": FunctionInfo(
        name="ADDRESS",
        category="Lookup & Reference",
        args=("row_num", "column_num", "[abs_num]", "[a1]", "[sheet_text]"),
        desc="Creates a cell reference as text, given specified row and column numbers.",
        classic=True,
    ),
    "AGGREGATE": FunctionInfo(
        name="AGGREGATE",
        category="Math & Trig",
        args=("function_num", "options", "ref1", "..."),
        desc=(
            "Returns an aggregate in a list or database, optionally ignoring hidden rows "
            "and error values."
        ),
        classic=False,
    ),
    "AMORDEGRC": FunctionInfo(
        name="AMORDEGRC",
        category="Financial",
        args=("cost", "date_purchased", "first_period", "salvage", "period", "rate", "[basis]"),
        desc=(
            "Returns the prorated linear depreciation of an asset for each accounting "
            "period, using a depreciation coefficient."
        ),
        classic=True,
    ),
    "AMORLINC": FunctionInfo(
        name="AMORLINC",
        category="Financial",
        args=("cost", "date_purchased", "first_period", "salvage", "period", "rate", "[basis]"),
        desc="Returns the prorated linear depreciation of an asset for each accounting period.",
        classic=True,
    ),
    "ANCHORARRAY": FunctionInfo(
        name="ANCHORARRAY",
        category="Lookup & Reference",
        args=("reference",),
        desc="Returns the spilled array range originating at the specified reference.",
        classic=False,
    ),
    "AND": FunctionInfo(
        name="AND",
        category="Logical",
        args=("logical1", "[logical2]", "..."),
        desc="Checks whether all arguments are TRUE, and returns TRUE if all arguments are TRUE.",
        classic=True,
    ),
    "ARABIC": FunctionInfo(
        name="ARABIC",
        category="Math & Trig",
        args=("text",),
        desc="Converts a Roman numeral to Arabic.",
        classic=False,
    ),
    "AREAS": FunctionInfo(
        name="AREAS",
        category="Lookup & Reference",
        args=("reference",),
        desc=(
            "Returns the number of areas in a reference. An area is a range of "
            "contiguous cells or a single cell."
        ),
        classic=True,
    ),
    "ARRAYTOTEXT": FunctionInfo(
        name="ARRAYTOTEXT",
        category="Text",
        args=("array", "[format]"),
        desc="Returns a text representation of an array.",
        classic=False,
    ),
    "ASC": FunctionInfo(
        name="ASC",
        category="Text",
        args=("text",),
        desc="Changes full-width (double-byte) characters to half-width (single-byte) characters.",
        classic=True,
    ),
    "ASIN": FunctionInfo(
        name="ASIN",
        category="Math & Trig",
        args=("number",),
        desc="Returns the arcsine of a number in radians, in the range -Pi/2 to Pi/2.",
        classic=True,
    ),
    "ASINH": FunctionInfo(
        name="ASINH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the inverse hyperbolic sine of a number.",
        classic=True,
    ),
    "ATAN": FunctionInfo(
        name="ATAN",
        category="Math & Trig",
        args=("number",),
        desc="Returns the arctangent of a number in radians, in the range -Pi/2 to Pi/2.",
        classic=True,
    ),
    "ATAN2": FunctionInfo(
        name="ATAN2",
        category="Math & Trig",
        args=("x_num", "y_num"),
        desc=(
            "Returns the arctangent of the specified x- and y- coordinates, in radians "
            "between -Pi and Pi, excluding -Pi."
        ),
        classic=True,
    ),
    "ATANH": FunctionInfo(
        name="ATANH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the inverse hyperbolic tangent of a number.",
        classic=True,
    ),
    "AVEDEV": FunctionInfo(
        name="AVEDEV",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the average of the absolute deviations of data points from their mean.",
        classic=True,
    ),
    "AVERAGE": FunctionInfo(
        name="AVERAGE",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the average (arithmetic mean) of its arguments, which can be "
            "numbers or names, arrays or references that contain numbers."
        ),
        classic=True,
    ),
    "AVERAGEA": FunctionInfo(
        name="AVERAGEA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Returns the average (arithmetic mean) of its arguments, evaluating text and "
            "FALSE in arguments as 0; TRUE evaluates as 1."
        ),
        classic=True,
    ),
    "AVERAGEIF": FunctionInfo(
        name="AVERAGEIF",
        category="Statistical",
        args=("range", "criteria", "[average_range]"),
        desc=(
            "Finds average (arithmetic mean) for the cells specified by a given "
            "condition or criteria."
        ),
        classic=False,
    ),
    "AVERAGEIFS": FunctionInfo(
        name="AVERAGEIFS",
        category="Statistical",
        args=("average_range", "criteria_range1", "criteria1", "..."),
        desc=(
            "Finds average (arithmetic mean) for the cells specified by a given set of "
            "conditions or criteria."
        ),
        classic=False,
    ),
    "BAHTTEXT": FunctionInfo(
        name="BAHTTEXT",
        category="Text",
        args=("number",),
        desc="Converts a number to text (baht).",
        classic=True,
    ),
    "BASE": FunctionInfo(
        name="BASE",
        category="Math & Trig",
        args=("number", "radix", "[min_length]"),
        desc="Converts a number into a text representation with the given radix (base).",
        classic=False,
    ),
    "BESSELI": FunctionInfo(
        name="BESSELI",
        category="Engineering",
        args=("x", "n"),
        desc="Returns the modified Bessel function In(x).",
        classic=True,
    ),
    "BESSELJ": FunctionInfo(
        name="BESSELJ",
        category="Engineering",
        args=("x", "n"),
        desc="Returns the Bessel function Jn(x).",
        classic=True,
    ),
    "BESSELK": FunctionInfo(
        name="BESSELK",
        category="Engineering",
        args=("x", "n"),
        desc="Returns the modified Bessel function Kn(x).",
        classic=True,
    ),
    "BESSELY": FunctionInfo(
        name="BESSELY",
        category="Engineering",
        args=("x", "n"),
        desc="Returns the Bessel function Yn(x).",
        classic=True,
    ),
    "BETA.DIST": FunctionInfo(
        name="BETA.DIST",
        category="Statistical",
        args=("x", "alpha", "beta", "cumulative", "[A]", "[B]"),
        desc="Returns the beta probability distribution function.",
        classic=False,
    ),
    "BETA.INV": FunctionInfo(
        name="BETA.INV",
        category="Statistical",
        args=("probability", "alpha", "beta", "[A]", "[B]"),
        desc="Returns the inverse of the cumulative beta probability density function.",
        classic=False,
    ),
    "BETADIST": FunctionInfo(
        name="BETADIST",
        category="Statistical",
        args=("x", "alpha", "beta", "[A]", "[B]"),
        desc="Returns the cumulative beta probability density function.",
        classic=True,
    ),
    "BETAINV": FunctionInfo(
        name="BETAINV",
        category="Statistical",
        args=("probability", "alpha", "beta", "[A]", "[B]"),
        desc="Returns the inverse of the cumulative beta probability density function.",
        classic=True,
    ),
    "BIN2DEC": FunctionInfo(
        name="BIN2DEC",
        category="Engineering",
        args=("number",),
        desc="Converts a binary number to decimal.",
        classic=True,
    ),
    "BIN2HEX": FunctionInfo(
        name="BIN2HEX",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a binary number to hexadecimal.",
        classic=True,
    ),
    "BIN2OCT": FunctionInfo(
        name="BIN2OCT",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a binary number to octal.",
        classic=True,
    ),
    "BINOM.DIST": FunctionInfo(
        name="BINOM.DIST",
        category="Statistical",
        args=("number_s", "trials", "probability_s", "cumulative"),
        desc="Returns the individual term binomial distribution probability.",
        classic=False,
    ),
    "BINOM.DIST.RANGE": FunctionInfo(
        name="BINOM.DIST.RANGE",
        category="Statistical",
        args=("trials", "probability_s", "number_s", "[number_s2]"),
        desc="Returns the probability of a trial result using a binomial distribution.",
        classic=False,
    ),
    "BINOM.INV": FunctionInfo(
        name="BINOM.INV",
        category="Statistical",
        args=("trials", "probability_s", "alpha"),
        desc=(
            "Returns the smallest value for which the cumulative binomial distribution "
            "is greater than or equal to a criterion value."
        ),
        classic=False,
    ),
    "BINOMDIST": FunctionInfo(
        name="BINOMDIST",
        category="Statistical",
        args=("number_s", "trials", "probability_s", "cumulative"),
        desc="Returns the individual term binomial distribution probability.",
        classic=True,
    ),
    "BITAND": FunctionInfo(
        name="BITAND",
        category="Engineering",
        args=("number1", "number2"),
        desc="Returns a bitwise 'And' of two numbers.",
        classic=False,
    ),
    "BITLSHIFT": FunctionInfo(
        name="BITLSHIFT",
        category="Engineering",
        args=("number", "shift_amount"),
        desc="Returns a number shifted left by shift_amount bits.",
        classic=False,
    ),
    "BITOR": FunctionInfo(
        name="BITOR",
        category="Engineering",
        args=("number1", "number2"),
        desc="Returns a bitwise 'Or' of two numbers.",
        classic=False,
    ),
    "BITRSHIFT": FunctionInfo(
        name="BITRSHIFT",
        category="Engineering",
        args=("number", "shift_amount"),
        desc="Returns a number shifted right by shift_amount bits.",
        classic=False,
    ),
    "BITXOR": FunctionInfo(
        name="BITXOR",
        category="Engineering",
        args=("number1", "number2"),
        desc="Returns a bitwise 'Exclusive Or' of two numbers.",
        classic=False,
    ),
    "BYCOL": FunctionInfo(
        name="BYCOL",
        category="Logical",
        args=("array", "lambda"),
        desc="Applies a LAMBDA to each column and returns an array of the results.",
        classic=False,
    ),
    "BYROW": FunctionInfo(
        name="BYROW",
        category="Logical",
        args=("array", "lambda"),
        desc="Applies a LAMBDA to each row and returns an array of the results.",
        classic=False,
    ),
    "CALL": FunctionInfo(
        name="CALL",
        category="Add-in & Automation",
        args=("module_text", "procedure", "[type_text]", "..."),
        desc="Calls a procedure in a dynamic link library or code resource.",
        classic=False,
    ),
    "CEILING": FunctionInfo(
        name="CEILING",
        category="Math & Trig",
        args=("number", "significance"),
        desc="Rounds a number up, to the nearest multiple of significance.",
        classic=True,
    ),
    "CEILING.MATH": FunctionInfo(
        name="CEILING.MATH",
        category="Math & Trig",
        args=("number", "[significance]", "[mode]"),
        desc=(
            "Rounds a number up, to the nearest integer or to the nearest multiple of significance."
        ),
        classic=False,
    ),
    "CEILING.PRECISE": FunctionInfo(
        name="CEILING.PRECISE",
        category="Math & Trig",
        args=("number", "[significance]"),
        desc=(
            "Rounds a number up to the nearest integer or to the nearest multiple of significance."
        ),
        classic=False,
    ),
    "CELL": FunctionInfo(
        name="CELL",
        category="Information",
        args=("info_type", "[reference]"),
        desc=(
            "Returns information about the formatting, location, or contents of the "
            "first cell, according to the sheet's reading order, in a reference."
        ),
        classic=True,
    ),
    "CHAR": FunctionInfo(
        name="CHAR",
        category="Text",
        args=("number",),
        desc=(
            "Returns the character specified by the code number from the character set "
            "for your computer."
        ),
        classic=True,
    ),
    "CHIDIST": FunctionInfo(
        name="CHIDIST",
        category="Statistical",
        args=("x", "deg_freedom"),
        desc="Returns the one-tailed probability of the chi-squared distribution.",
        classic=True,
    ),
    "CHIINV": FunctionInfo(
        name="CHIINV",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the inverse of the one-tailed probability of the chi-squared distribution.",
        classic=True,
    ),
    "CHISQ.DIST": FunctionInfo(
        name="CHISQ.DIST",
        category="Statistical",
        args=("x", "deg_freedom", "cumulative"),
        desc="Returns the left-tailed probability of the chi-squared distribution.",
        classic=False,
    ),
    "CHISQ.DIST.RT": FunctionInfo(
        name="CHISQ.DIST.RT",
        category="Statistical",
        args=("x", "deg_freedom"),
        desc="Returns the right-tailed probability of the chi-squared distribution.",
        classic=False,
    ),
    "CHISQ.INV": FunctionInfo(
        name="CHISQ.INV",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the inverse of the left-tailed probability of the chi-squared distribution.",
        classic=False,
    ),
    "CHISQ.INV.RT": FunctionInfo(
        name="CHISQ.INV.RT",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the inverse of the right-tailed probability of the chi-squared distribution.",
        classic=False,
    ),
    "CHISQ.TEST": FunctionInfo(
        name="CHISQ.TEST",
        category="Statistical",
        args=("actual_range", "expected_range"),
        desc="Returns the test for independence.",
        classic=False,
    ),
    "CHITEST": FunctionInfo(
        name="CHITEST",
        category="Statistical",
        args=("actual_range", "expected_range"),
        desc=(
            "Returns the test for independence: the value from the chi-squared "
            "distribution for the statistic and the appropriate degrees of freedom."
        ),
        classic=True,
    ),
    "CHOOSE": FunctionInfo(
        name="CHOOSE",
        category="Lookup & Reference",
        args=("index_num", "value1", "[value2]", "..."),
        desc=(
            "Chooses a value or action to perform from a list of values, based on an index number."
        ),
        classic=True,
    ),
    "CHOOSECOLS": FunctionInfo(
        name="CHOOSECOLS",
        category="Lookup & Reference",
        args=("array", "col_num1", "..."),
        desc="Returns the specified columns from an array.",
        classic=False,
    ),
    "CHOOSEROWS": FunctionInfo(
        name="CHOOSEROWS",
        category="Lookup & Reference",
        args=("array", "row_num1", "..."),
        desc="Returns the specified rows from an array.",
        classic=False,
    ),
    "CLEAN": FunctionInfo(
        name="CLEAN",
        category="Text",
        args=("text",),
        desc="Removes all nonprintable characters from text.",
        classic=True,
    ),
    "CODE": FunctionInfo(
        name="CODE",
        category="Text",
        args=("text",),
        desc=(
            "Returns a numeric code for the first character in a text string, in the "
            "character set used by your computer."
        ),
        classic=True,
    ),
    "COLUMN": FunctionInfo(
        name="COLUMN",
        category="Lookup & Reference",
        args=("[reference]",),
        desc="Returns the column number of a reference.",
        classic=True,
    ),
    "COLUMNS": FunctionInfo(
        name="COLUMNS",
        category="Lookup & Reference",
        args=("array",),
        desc="Returns the number of columns in an array or reference.",
        classic=True,
    ),
    "COMBIN": FunctionInfo(
        name="COMBIN",
        category="Math & Trig",
        args=("number", "number_chosen"),
        desc="Returns the number of combinations for a given number of items.",
        classic=True,
    ),
    "COMBINA": FunctionInfo(
        name="COMBINA",
        category="Math & Trig",
        args=("number", "number_chosen"),
        desc="Returns the number of combinations with repetitions for a given number of items.",
        classic=False,
    ),
    "COMPLEX": FunctionInfo(
        name="COMPLEX",
        category="Engineering",
        args=("real_num", "i_num", "[suffix]"),
        desc="Converts real and imaginary coefficients into a complex number.",
        classic=True,
    ),
    "CONCAT": FunctionInfo(
        name="CONCAT",
        category="Text",
        args=("text1", "..."),
        desc="Concatenates a list or range of text strings.",
        classic=False,
    ),
    "CONCATENATE": FunctionInfo(
        name="CONCATENATE",
        category="Text",
        args=("text1", "[text2]", "..."),
        desc="Joins several text strings into one text string.",
        classic=True,
    ),
    "CONFIDENCE": FunctionInfo(
        name="CONFIDENCE",
        category="Statistical",
        args=("alpha", "standard_dev", "size"),
        desc="Returns the confidence interval for a population mean.",
        classic=True,
    ),
    "CONFIDENCE.NORM": FunctionInfo(
        name="CONFIDENCE.NORM",
        category="Statistical",
        args=("alpha", "standard_dev", "size"),
        desc="Returns the confidence interval for a population mean, using a normal distribution.",
        classic=False,
    ),
    "CONFIDENCE.T": FunctionInfo(
        name="CONFIDENCE.T",
        category="Statistical",
        args=("alpha", "standard_dev", "size"),
        desc=(
            "Returns the confidence interval for a population mean, using a Student's T "
            "distribution."
        ),
        classic=False,
    ),
    "CONVERT": FunctionInfo(
        name="CONVERT",
        category="Engineering",
        args=("number", "from_unit", "to_unit"),
        desc="Converts a number from one measurement system to another.",
        classic=True,
    ),
    "COPILOT": FunctionInfo(
        name="COPILOT",
        category="Add-in & Automation",
        args=("prompt", "[context]"),
        desc="Invokes AI assistant with prompt and optional context.",
        classic=False,
    ),
    "CORREL": FunctionInfo(
        name="CORREL",
        category="Statistical",
        args=("array1", "array2"),
        desc="Returns the correlation coefficient between two data sets.",
        classic=True,
    ),
    "COS": FunctionInfo(
        name="COS",
        category="Math & Trig",
        args=("number",),
        desc="Returns the cosine of an angle.",
        classic=True,
    ),
    "COSH": FunctionInfo(
        name="COSH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic cosine of a number.",
        classic=True,
    ),
    "COT": FunctionInfo(
        name="COT",
        category="Math & Trig",
        args=("number",),
        desc="Returns the cotangent of an angle.",
        classic=False,
    ),
    "COTH": FunctionInfo(
        name="COTH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic cotangent of a number.",
        classic=False,
    ),
    "COUNT": FunctionInfo(
        name="COUNT",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc="Counts the number of cells in a range that contain numbers.",
        classic=True,
    ),
    "COUNTA": FunctionInfo(
        name="COUNTA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc="Counts the number of cells in a range that are not empty.",
        classic=True,
    ),
    "COUNTBLANK": FunctionInfo(
        name="COUNTBLANK",
        category="Statistical",
        args=("range",),
        desc="Counts the number of empty cells in a specified range of cells.",
        classic=True,
    ),
    "COUNTIF": FunctionInfo(
        name="COUNTIF",
        category="Statistical",
        args=("range", "criteria"),
        desc="Counts the number of cells within a range that meet the given condition.",
        classic=True,
    ),
    "COUNTIFS": FunctionInfo(
        name="COUNTIFS",
        category="Statistical",
        args=("criteria_range1", "criteria1", "..."),
        desc="Counts the number of cells specified by a given set of conditions or criteria.",
        classic=False,
    ),
    "COUPDAYBS": FunctionInfo(
        name="COUPDAYBS",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc=(
            "Returns the number of days from the beginning of the coupon period to the "
            "settlement date."
        ),
        classic=True,
    ),
    "COUPDAYS": FunctionInfo(
        name="COUPDAYS",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc="Returns the number of days in the coupon period that contains the settlement date.",
        classic=True,
    ),
    "COUPDAYSNC": FunctionInfo(
        name="COUPDAYSNC",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc="Returns the number of days from the settlement date to the next coupon date.",
        classic=True,
    ),
    "COUPNCD": FunctionInfo(
        name="COUPNCD",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc="Returns the next coupon date after the settlement date.",
        classic=True,
    ),
    "COUPNUM": FunctionInfo(
        name="COUPNUM",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc="Returns the number of coupons payable between the settlement date and maturity date.",
        classic=True,
    ),
    "COUPPCD": FunctionInfo(
        name="COUPPCD",
        category="Financial",
        args=("settlement", "maturity", "frequency", "[basis]"),
        desc="Returns the previous coupon date before the settlement date.",
        classic=True,
    ),
    "COVAR": FunctionInfo(
        name="COVAR",
        category="Statistical",
        args=("array1", "array2"),
        desc=(
            "Returns covariance, the average of the products of deviations for each data "
            "point pair in two data sets."
        ),
        classic=True,
    ),
    "COVARIANCE.P": FunctionInfo(
        name="COVARIANCE.P",
        category="Statistical",
        args=("array1", "array2"),
        desc=(
            "Returns population covariance, the average of the products of deviations "
            "for each data point pair in two data sets."
        ),
        classic=False,
    ),
    "COVARIANCE.S": FunctionInfo(
        name="COVARIANCE.S",
        category="Statistical",
        args=("array1", "array2"),
        desc=(
            "Returns the sample covariance, the average of the products of deviations "
            "for each data point pair in two data sets."
        ),
        classic=False,
    ),
    "CRITBINOM": FunctionInfo(
        name="CRITBINOM",
        category="Statistical",
        args=("trials", "probability_s", "alpha"),
        desc=(
            "Returns the smallest value for which the cumulative binomial distribution "
            "is greater than or equal to a criterion value."
        ),
        classic=True,
    ),
    "CSC": FunctionInfo(
        name="CSC",
        category="Math & Trig",
        args=("number",),
        desc="Returns the cosecant of an angle.",
        classic=False,
    ),
    "CSCH": FunctionInfo(
        name="CSCH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic cosecant of an angle.",
        classic=False,
    ),
    "CUBEKPIMEMBER": FunctionInfo(
        name="CUBEKPIMEMBER",
        category="Cube",
        args=("connection", "kpi_name", "kpi_property", "[caption]"),
        desc=(
            "Returns a key performance indicator (KPI) property and displays the KPI "
            "name in the cell."
        ),
        classic=False,
    ),
    "CUBEMEMBER": FunctionInfo(
        name="CUBEMEMBER",
        category="Cube",
        args=("connection", "member_expression", "[caption]"),
        desc="Returns a member or tuple from the cube.",
        classic=False,
    ),
    "CUBEMEMBERPROPERTY": FunctionInfo(
        name="CUBEMEMBERPROPERTY",
        category="Cube",
        args=("connection", "member_expression", "property"),
        desc="Returns the value of a member property from the cube.",
        classic=False,
    ),
    "CUBERANKEDMEMBER": FunctionInfo(
        name="CUBERANKEDMEMBER",
        category="Cube",
        args=("connection", "set_expression", "rank", "[caption]"),
        desc="Returns the nth, or ranked, member in a set.",
        classic=False,
    ),
    "CUBESET": FunctionInfo(
        name="CUBESET",
        category="Cube",
        args=("connection", "set_expression", "[caption]", "[sort_order]", "[sort_by]"),
        desc=(
            "Defines a calculated set of members or tuples by sending a set expression "
            "to the cube on the server."
        ),
        classic=False,
    ),
    "CUBESETCOUNT": FunctionInfo(
        name="CUBESETCOUNT",
        category="Cube",
        args=("set",),
        desc="Returns the number of items in a set.",
        classic=False,
    ),
    "CUBEVALUE": FunctionInfo(
        name="CUBEVALUE",
        category="Cube",
        args=("connection", "[member_expression1]", "..."),
        desc="Returns an aggregated value from the cube.",
        classic=False,
    ),
    "CUMIPMT": FunctionInfo(
        name="CUMIPMT",
        category="Financial",
        args=("rate", "nper", "pv", "start_period", "end_period", "type"),
        desc="Returns the cumulative interest paid between two periods.",
        classic=True,
    ),
    "CUMPRINC": FunctionInfo(
        name="CUMPRINC",
        category="Financial",
        args=("rate", "nper", "pv", "start_period", "end_period", "type"),
        desc="Returns the cumulative principal paid on a loan between two periods.",
        classic=True,
    ),
    "DATE": FunctionInfo(
        name="DATE",
        category="Date & Time",
        args=("year", "month", "day"),
        desc="Returns the number that represents the date in Ledger date-time code.",
        classic=True,
    ),
    "DATEDIF": FunctionInfo(
        name="DATEDIF",
        category="Date & Time",
        args=("start_date", "end_date", "unit"),
        desc="Calculates the number of days, months or years between two dates.",
        classic=False,
    ),
    "DATEVALUE": FunctionInfo(
        name="DATEVALUE",
        category="Date & Time",
        args=("date_text",),
        desc=(
            "Converts a date in the form of text to a number that represents the date in "
            "Ledger date-time code."
        ),
        classic=True,
    ),
    "DAVERAGE": FunctionInfo(
        name="DAVERAGE",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Averages the values in a column in a list or database that match conditions "
            "you specify."
        ),
        classic=True,
    ),
    "DAY": FunctionInfo(
        name="DAY",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the day of the month, a number from 1 to 31.",
        classic=True,
    ),
    "DAYS": FunctionInfo(
        name="DAYS",
        category="Date & Time",
        args=("end_date", "start_date"),
        desc="Returns the number of days between the two dates.",
        classic=False,
    ),
    "DAYS360": FunctionInfo(
        name="DAYS360",
        category="Date & Time",
        args=("start_date", "end_date", "[method]"),
        desc=(
            "Returns the number of days between two dates based on a 360-day year "
            "(twelve 30-day months)."
        ),
        classic=True,
    ),
    "DB": FunctionInfo(
        name="DB",
        category="Financial",
        args=("cost", "salvage", "life", "period", "[month]"),
        desc=(
            "Returns the depreciation of an asset for a specified period using the "
            "fixed-declining balance method."
        ),
        classic=True,
    ),
    "DBCS": FunctionInfo(
        name="DBCS",
        category="Text",
        args=("text",),
        desc="Changes half-width (single-byte) characters to full-width (double-byte) characters.",
        classic=False,
    ),
    "DCOUNT": FunctionInfo(
        name="DCOUNT",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Counts the cells containing numbers in the field (column) of records in the "
            "database that match the conditions you specify."
        ),
        classic=True,
    ),
    "DCOUNTA": FunctionInfo(
        name="DCOUNTA",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Counts nonblank cells in the field (column) of records in the database that "
            "match the conditions you specify."
        ),
        classic=True,
    ),
    "DDB": FunctionInfo(
        name="DDB",
        category="Financial",
        args=("cost", "salvage", "life", "period", "[factor]"),
        desc=(
            "Returns the depreciation of an asset for a specified period using the "
            "double-declining balance method or some other method you specify."
        ),
        classic=True,
    ),
    "DEC2BIN": FunctionInfo(
        name="DEC2BIN",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a decimal number to binary.",
        classic=True,
    ),
    "DEC2HEX": FunctionInfo(
        name="DEC2HEX",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a decimal number to hexadecimal.",
        classic=True,
    ),
    "DEC2OCT": FunctionInfo(
        name="DEC2OCT",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a decimal number to octal.",
        classic=True,
    ),
    "DECIMAL": FunctionInfo(
        name="DECIMAL",
        category="Math & Trig",
        args=("number", "radix"),
        desc="Converts a text representation of a number in a given base into a decimal number.",
        classic=False,
    ),
    "DEGREES": FunctionInfo(
        name="DEGREES",
        category="Math & Trig",
        args=("angle",),
        desc="Converts radians to degrees.",
        classic=True,
    ),
    "DELTA": FunctionInfo(
        name="DELTA",
        category="Engineering",
        args=("number1", "[number2]"),
        desc="Tests whether two numbers are equal.",
        classic=True,
    ),
    "DETECTLANGUAGE": FunctionInfo(
        name="DETECTLANGUAGE",
        category="Web",
        args=("text",),
        desc="Detects the language of specified text.",
        classic=False,
    ),
    "DEVSQ": FunctionInfo(
        name="DEVSQ",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the sum of squares of deviations of data points from their sample mean.",
        classic=True,
    ),
    "DGET": FunctionInfo(
        name="DGET",
        category="Database",
        args=("database", "field", "criteria"),
        desc="Extracts from a database a single record that matches the conditions you specify.",
        classic=True,
    ),
    "DISC": FunctionInfo(
        name="DISC",
        category="Financial",
        args=("settlement", "maturity", "pr", "redemption", "[basis]"),
        desc="Returns the discount rate for a security.",
        classic=True,
    ),
    "DMAX": FunctionInfo(
        name="DMAX",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Returns the largest number in the field (column) of records in the database "
            "that match the conditions you specify."
        ),
        classic=True,
    ),
    "DMIN": FunctionInfo(
        name="DMIN",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Returns the smallest number in the field (column) of records in the "
            "database that match the conditions you specify."
        ),
        classic=True,
    ),
    "DOLLAR": FunctionInfo(
        name="DOLLAR",
        category="Text",
        args=("number", "[decimals]"),
        desc="Converts a number to text, using currency format.",
        classic=True,
    ),
    "DOLLARDE": FunctionInfo(
        name="DOLLARDE",
        category="Financial",
        args=("fractional_dollar", "fraction"),
        desc=(
            "Converts a dollar price, expressed as a fraction, into a dollar price, "
            "expressed as a decimal number."
        ),
        classic=True,
    ),
    "DOLLARFR": FunctionInfo(
        name="DOLLARFR",
        category="Financial",
        args=("decimal_dollar", "fraction"),
        desc=(
            "Converts a dollar price, expressed as a decimal number, into a dollar "
            "price, expressed as a fraction."
        ),
        classic=True,
    ),
    "DPRODUCT": FunctionInfo(
        name="DPRODUCT",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Multiplies the values in the field (column) of records in the database that "
            "match the conditions you specify."
        ),
        classic=True,
    ),
    "DROP": FunctionInfo(
        name="DROP",
        category="Lookup & Reference",
        args=("array", "rows", "[columns]"),
        desc="Drops rows or columns from the start or end of an array.",
        classic=False,
    ),
    "DSTDEV": FunctionInfo(
        name="DSTDEV",
        category="Database",
        args=("database", "field", "criteria"),
        desc="Estimates the standard deviation based on a sample from selected database entries.",
        classic=True,
    ),
    "DSTDEVP": FunctionInfo(
        name="DSTDEVP",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Calculates the standard deviation based on the entire population of "
            "selected database entries."
        ),
        classic=True,
    ),
    "DSUM": FunctionInfo(
        name="DSUM",
        category="Database",
        args=("database", "field", "criteria"),
        desc=(
            "Adds the numbers in the field (column) of records in the database that "
            "match the conditions you specify."
        ),
        classic=True,
    ),
    "DURATION": FunctionInfo(
        name="DURATION",
        category="Financial",
        args=("settlement", "maturity", "coupon", "yld", "frequency", "[basis]"),
        desc="Returns the annual duration of a security with periodic interest payments.",
        classic=True,
    ),
    "DVAR": FunctionInfo(
        name="DVAR",
        category="Database",
        args=("database", "field", "criteria"),
        desc="Estimates variance based on a sample from selected database entries.",
        classic=True,
    ),
    "DVARP": FunctionInfo(
        name="DVARP",
        category="Database",
        args=("database", "field", "criteria"),
        desc="Calculates variance based on the entire population of selected database entries.",
        classic=True,
    ),
    "ECMA.CEILING": FunctionInfo(
        name="ECMA.CEILING",
        category="Math & Trig",
        args=("number", "significance"),
        desc="Rounds a number up to the nearest multiple of significance.",
        classic=False,
    ),
    "EDATE": FunctionInfo(
        name="EDATE",
        category="Date & Time",
        args=("start_date", "months"),
        desc=(
            "Returns the serial number of the date that is the indicated number of "
            "months before or after the start date."
        ),
        classic=True,
    ),
    "EFFECT": FunctionInfo(
        name="EFFECT",
        category="Financial",
        args=("nominal_rate", "npery"),
        desc="Returns the effective annual interest rate.",
        classic=True,
    ),
    "EOMONTH": FunctionInfo(
        name="EOMONTH",
        category="Date & Time",
        args=("start_date", "months"),
        desc=(
            "Returns the serial number of the last day of the month before or after a "
            "specified number of months."
        ),
        classic=True,
    ),
    "ERF": FunctionInfo(
        name="ERF",
        category="Engineering",
        args=("lower_limit", "[upper_limit]"),
        desc="Returns the error function.",
        classic=True,
    ),
    "ERF.PRECISE": FunctionInfo(
        name="ERF.PRECISE",
        category="Engineering",
        args=("x",),
        desc="Returns the error function.",
        classic=False,
    ),
    "ERFC": FunctionInfo(
        name="ERFC",
        category="Engineering",
        args=("x",),
        desc="Returns the complementary error function.",
        classic=True,
    ),
    "ERFC.PRECISE": FunctionInfo(
        name="ERFC.PRECISE",
        category="Engineering",
        args=("x",),
        desc="Returns the complementary error function.",
        classic=False,
    ),
    "ERROR.TYPE": FunctionInfo(
        name="ERROR.TYPE",
        category="Information",
        args=("error_val",),
        desc="Returns a number corresponding to an error value.",
        classic=True,
    ),
    "EUROCONVERT": FunctionInfo(
        name="EUROCONVERT",
        category="Financial",
        args=("number", "source", "target", "[full_precision]", "[triangulation_precision]"),
        desc="Converts a number to euros, or converts from euros to a euro member currency.",
        classic=False,
    ),
    "EVEN": FunctionInfo(
        name="EVEN",
        category="Math & Trig",
        args=("number",),
        desc="Rounds a positive number up and negative number down to the nearest even integer.",
        classic=True,
    ),
    "EXACT": FunctionInfo(
        name="EXACT",
        category="Text",
        args=("text1", "text2"),
        desc=(
            "Checks whether two text strings are exactly the same, and returns TRUE or "
            "FALSE. EXACT is case-sensitive."
        ),
        classic=True,
    ),
    "EXP": FunctionInfo(
        name="EXP",
        category="Math & Trig",
        args=("number",),
        desc="Returns e raised to the power of a given number.",
        classic=True,
    ),
    "EXPAND": FunctionInfo(
        name="EXPAND",
        category="Lookup & Reference",
        args=("array", "rows", "[columns]", "[pad_with]"),
        desc="Expands an array to the specified dimensions.",
        classic=False,
    ),
    "EXPON.DIST": FunctionInfo(
        name="EXPON.DIST",
        category="Statistical",
        args=("x", "lambda", "cumulative"),
        desc="Returns the exponential distribution.",
        classic=False,
    ),
    "EXPONDIST": FunctionInfo(
        name="EXPONDIST",
        category="Statistical",
        args=("x", "lambda", "cumulative"),
        desc="Returns the exponential distribution.",
        classic=True,
    ),
    "F.DIST": FunctionInfo(
        name="F.DIST",
        category="Statistical",
        args=("x", "deg_freedom1", "deg_freedom2", "cumulative"),
        desc=(
            "Returns the (left-tailed) F probability distribution (degree of diversity) "
            "for two data sets."
        ),
        classic=False,
    ),
    "F.DIST.RT": FunctionInfo(
        name="F.DIST.RT",
        category="Statistical",
        args=("x", "deg_freedom1", "deg_freedom2"),
        desc=(
            "Returns the (right-tailed) F probability distribution (degree of diversity) "
            "for two data sets."
        ),
        classic=False,
    ),
    "F.INV": FunctionInfo(
        name="F.INV",
        category="Statistical",
        args=("probability", "deg_freedom1", "deg_freedom2"),
        desc="Returns the inverse of the (left-tailed) F probability distribution.",
        classic=False,
    ),
    "F.INV.RT": FunctionInfo(
        name="F.INV.RT",
        category="Statistical",
        args=("probability", "deg_freedom1", "deg_freedom2"),
        desc="Returns the inverse of the (right-tailed) F probability distribution.",
        classic=False,
    ),
    "F.TEST": FunctionInfo(
        name="F.TEST",
        category="Statistical",
        args=("array1", "array2"),
        desc=(
            "Returns the result of an F-test, the two-tailed probability that the "
            "variances in Array1 and Array2 are not significantly different."
        ),
        classic=False,
    ),
    "FACT": FunctionInfo(
        name="FACT",
        category="Math & Trig",
        args=("number",),
        desc="Returns the factorial of a number, equal to 1*2*3*...* Number.",
        classic=True,
    ),
    "FACTDOUBLE": FunctionInfo(
        name="FACTDOUBLE",
        category="Math & Trig",
        args=("number",),
        desc="Returns the double factorial of a number.",
        classic=True,
    ),
    "FALSE": FunctionInfo(
        name="FALSE",
        category="Logical",
        args=(),
        desc="Returns the logical value FALSE.",
        classic=True,
    ),
    "FDIST": FunctionInfo(
        name="FDIST",
        category="Statistical",
        args=("x", "deg_freedom1", "deg_freedom2"),
        desc="Returns the F probability distribution (degree of diversity) for two data sets.",
        classic=True,
    ),
    "FILTER": FunctionInfo(
        name="FILTER",
        category="Lookup & Reference",
        args=("array", "include", "[if_empty]"),
        desc="Filters a range or array.",
        classic=False,
    ),
    "FILTERXML": FunctionInfo(
        name="FILTERXML",
        category="Web",
        args=("xml", "xpath"),
        desc="Returns specific data from the XML content by using the specified XPath.",
        classic=False,
    ),
    "FIND": FunctionInfo(
        name="FIND",
        category="Text",
        args=("find_text", "within_text", "[start_num]"),
        desc=(
            "Returns the starting position of one text string within another text "
            "string. FIND is case-sensitive."
        ),
        classic=True,
    ),
    "FINDB": FunctionInfo(
        name="FINDB",
        category="Text",
        args=("find_text", "within_text", "[start_num]"),
        desc=(
            "Finds the starting position of one text string within another text string, "
            "counting bytes."
        ),
        classic=True,
    ),
    "FINV": FunctionInfo(
        name="FINV",
        category="Statistical",
        args=("probability", "deg_freedom1", "deg_freedom2"),
        desc="Returns the inverse of the F probability distribution.",
        classic=True,
    ),
    "FISHER": FunctionInfo(
        name="FISHER",
        category="Statistical",
        args=("x",),
        desc="Returns the Fisher transformation.",
        classic=True,
    ),
    "FISHERINV": FunctionInfo(
        name="FISHERINV",
        category="Statistical",
        args=("y",),
        desc="Returns the inverse of the Fisher transformation.",
        classic=True,
    ),
    "FIXED": FunctionInfo(
        name="FIXED",
        category="Text",
        args=("number", "[decimals]", "[no_commas]"),
        desc=(
            "Rounds a number to the specified number of decimals and returns the result "
            "as text with or without commas."
        ),
        classic=True,
    ),
    "FLOOR": FunctionInfo(
        name="FLOOR",
        category="Math & Trig",
        args=("number", "significance"),
        desc="Rounds a number down to the nearest multiple of significance.",
        classic=True,
    ),
    "FLOOR.MATH": FunctionInfo(
        name="FLOOR.MATH",
        category="Math & Trig",
        args=("number", "[significance]", "[mode]"),
        desc=(
            "Rounds a number down, to the nearest integer or to the nearest multiple of "
            "significance."
        ),
        classic=False,
    ),
    "FLOOR.PRECISE": FunctionInfo(
        name="FLOOR.PRECISE",
        category="Math & Trig",
        args=("number", "[significance]"),
        desc=(
            "Rounds a number down to the nearest integer or to the nearest multiple of "
            "significance."
        ),
        classic=False,
    ),
    "FORECAST": FunctionInfo(
        name="FORECAST",
        category="Statistical",
        args=("x", "known_y's", "known_x's"),
        desc=(
            "Calculates, or predicts, a future value along a linear trend by using existing values."
        ),
        classic=True,
    ),
    "FORECAST.ETS": FunctionInfo(
        name="FORECAST.ETS",
        category="Statistical",
        args=(
            "target_date",
            "values",
            "timeline",
            "[seasonality]",
            "[data_completion]",
            "[aggregation]",
        ),
        desc="Calculates or predicts a future value based on existing values using ETS.",
        classic=False,
    ),
    "FORECAST.ETS.CONFINT": FunctionInfo(
        name="FORECAST.ETS.CONFINT",
        category="Statistical",
        args=(
            "target_date",
            "values",
            "timeline",
            "[confidence_level]",
            "[seasonality]",
            "[data_completion]",
            "[aggregation]",
        ),
        desc="Returns confidence interval for forecast value at target date.",
        classic=False,
    ),
    "FORECAST.ETS.SEASONALITY": FunctionInfo(
        name="FORECAST.ETS.SEASONALITY",
        category="Statistical",
        args=("values", "timeline", "[data_completion]", "[aggregation]"),
        desc=(
            "Returns the length of the repetitive pattern Excel detects for the "
            "specified time series."
        ),
        classic=False,
    ),
    "FORECAST.ETS.STAT": FunctionInfo(
        name="FORECAST.ETS.STAT",
        category="Statistical",
        args=(
            "values",
            "timeline",
            "statistic_type",
            "[seasonality]",
            "[data_completion]",
            "[aggregation]",
        ),
        desc="Returns a statistical value as a result of time series forecasting.",
        classic=False,
    ),
    "FORECAST.LINEAR": FunctionInfo(
        name="FORECAST.LINEAR",
        category="Statistical",
        args=("x", "known_y's", "known_x's"),
        desc=(
            "Calculates, or predicts, a future value along a linear trend by using existing values."
        ),
        classic=False,
    ),
    "FORMULATEXT": FunctionInfo(
        name="FORMULATEXT",
        category="Lookup & Reference",
        args=("reference",),
        desc="Returns a formula as a string.",
        classic=False,
    ),
    "FREQUENCY": FunctionInfo(
        name="FREQUENCY",
        category="Statistical",
        args=("data_array", "bins_array"),
        desc=(
            "Calculates how often values occur within a range of values and then returns "
            "a vertical array of numbers having one more element than Bins_array."
        ),
        classic=True,
    ),
    "FTEST": FunctionInfo(
        name="FTEST",
        category="Statistical",
        args=("array1", "array2"),
        desc=(
            "Returns the result of an F-test, the two-tailed probability that the "
            "variances in Array1 and Array2 are not significantly different."
        ),
        classic=True,
    ),
    "FV": FunctionInfo(
        name="FV",
        category="Financial",
        args=("rate", "nper", "pmt", "[pv]", "[type]"),
        desc=(
            "Returns the future value of an investment based on periodic, constant "
            "payments and a constant interest rate."
        ),
        classic=True,
    ),
    "FVSCHEDULE": FunctionInfo(
        name="FVSCHEDULE",
        category="Financial",
        args=("principal", "schedule"),
        desc=(
            "Returns the future value of an initial principal after applying a series of "
            "compound interest rates."
        ),
        classic=True,
    ),
    "GAMMA": FunctionInfo(
        name="GAMMA",
        category="Statistical",
        args=("x",),
        desc="Returns the Gamma function value.",
        classic=False,
    ),
    "GAMMA.DIST": FunctionInfo(
        name="GAMMA.DIST",
        category="Statistical",
        args=("x", "alpha", "beta", "cumulative"),
        desc="Returns the gamma distribution.",
        classic=False,
    ),
    "GAMMA.INV": FunctionInfo(
        name="GAMMA.INV",
        category="Statistical",
        args=("probability", "alpha", "beta"),
        desc="Returns the inverse of the gamma cumulative distribution.",
        classic=False,
    ),
    "GAMMADIST": FunctionInfo(
        name="GAMMADIST",
        category="Statistical",
        args=("x", "alpha", "beta", "cumulative"),
        desc="Returns the gamma distribution.",
        classic=True,
    ),
    "GAMMAINV": FunctionInfo(
        name="GAMMAINV",
        category="Statistical",
        args=("probability", "alpha", "beta"),
        desc="Returns the inverse of the gamma cumulative distribution.",
        classic=True,
    ),
    "GAMMALN": FunctionInfo(
        name="GAMMALN",
        category="Statistical",
        args=("x",),
        desc="Returns the natural logarithm of the gamma function.",
        classic=True,
    ),
    "GAMMALN.PRECISE": FunctionInfo(
        name="GAMMALN.PRECISE",
        category="Statistical",
        args=("x",),
        desc="Returns the natural logarithm of the gamma function.",
        classic=False,
    ),
    "GAUSS": FunctionInfo(
        name="GAUSS",
        category="Statistical",
        args=("x",),
        desc="Returns 0.5 less than the standard normal cumulative distribution.",
        classic=False,
    ),
    "GCD": FunctionInfo(
        name="GCD",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc="Returns the greatest common divisor.",
        classic=True,
    ),
    "GEOMEAN": FunctionInfo(
        name="GEOMEAN",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the geometric mean of an array or range of positive numeric data.",
        classic=True,
    ),
    "GESTEP": FunctionInfo(
        name="GESTEP",
        category="Engineering",
        args=("number", "[step]"),
        desc="Tests whether a number is greater than a threshold value.",
        classic=True,
    ),
    "GETPIVOTDATA": FunctionInfo(
        name="GETPIVOTDATA",
        category="Lookup & Reference",
        args=("data_field", "pivot_table", "[field1]", "[item1]", "..."),
        desc="Extracts data stored in a PivotTable.",
        classic=True,
    ),
    "GROWTH": FunctionInfo(
        name="GROWTH",
        category="Statistical",
        args=("known_y's", "[known_x's]", "[new_x's]", "[const]"),
        desc="Returns numbers in an exponential growth trend matching known data points.",
        classic=True,
    ),
    "HARMEAN": FunctionInfo(
        name="HARMEAN",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the harmonic mean of a data set of positive numbers: the reciprocal "
            "of the arithmetic mean of reciprocals."
        ),
        classic=True,
    ),
    "HEX2BIN": FunctionInfo(
        name="HEX2BIN",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a hexadecimal number to binary.",
        classic=True,
    ),
    "HEX2DEC": FunctionInfo(
        name="HEX2DEC",
        category="Engineering",
        args=("number",),
        desc="Converts a hexadecimal number to decimal.",
        classic=True,
    ),
    "HEX2OCT": FunctionInfo(
        name="HEX2OCT",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts a hexadecimal number to octal.",
        classic=True,
    ),
    "HLOOKUP": FunctionInfo(
        name="HLOOKUP",
        category="Lookup & Reference",
        args=("lookup_value", "table_array", "row_index_num", "[range_lookup]"),
        desc=(
            "Looks for a value in the top row of a table or array of values and returns "
            "the value in the same column from a row you specify."
        ),
        classic=True,
    ),
    "HOUR": FunctionInfo(
        name="HOUR",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the hour as a number from 0 (12:00 A.M.) to 23 (11:00 P.M.).",
        classic=True,
    ),
    "HSTACK": FunctionInfo(
        name="HSTACK",
        category="Lookup & Reference",
        args=("array1", "[array2]", "..."),
        desc="Appends arrays horizontally and in sequence.",
        classic=False,
    ),
    "HYPERLINK": FunctionInfo(
        name="HYPERLINK",
        category="Lookup & Reference",
        args=("link_location", "[friendly_name]"),
        desc=(
            "Creates a shortcut or jump that opens a document stored on your hard drive, "
            "a network server, or on the Internet."
        ),
        classic=True,
    ),
    "HYPGEOM.DIST": FunctionInfo(
        name="HYPGEOM.DIST",
        category="Statistical",
        args=("sample_s", "number_sample", "population_s", "number_pop", "cumulative"),
        desc="Returns the hypergeometric distribution.",
        classic=False,
    ),
    "HYPGEOMDIST": FunctionInfo(
        name="HYPGEOMDIST",
        category="Statistical",
        args=("sample_s", "number_sample", "population_s", "number_pop"),
        desc="Returns the hypergeometric distribution.",
        classic=True,
    ),
    "IF": FunctionInfo(
        name="IF",
        category="Logical",
        args=("logical_test", "[value_if_true]", "[value_if_false]"),
        desc=(
            "Checks whether a condition is met, and returns one value if TRUE, and "
            "another value if FALSE."
        ),
        classic=True,
    ),
    "IFERROR": FunctionInfo(
        name="IFERROR",
        category="Logical",
        args=("value", "value_if_error"),
        desc=(
            "Returns value_if_error if expression is an error and the value of the "
            "expression itself otherwise."
        ),
        classic=False,
    ),
    "IFNA": FunctionInfo(
        name="IFNA",
        category="Logical",
        args=("value", "value_if_na"),
        desc=(
            "Returns the value you specify if the expression resolves to #N/A, otherwise "
            "returns the result of the expression."
        ),
        classic=False,
    ),
    "IFS": FunctionInfo(
        name="IFS",
        category="Logical",
        args=("logical_test1", "value_if_true1", "..."),
        desc=(
            "Checks whether one or more conditions are met and returns a value "
            "corresponding to the first TRUE condition."
        ),
        classic=False,
    ),
    "IMABS": FunctionInfo(
        name="IMABS",
        category="Engineering",
        args=("inumber",),
        desc="Returns the absolute value (modulus) of a complex number.",
        classic=True,
    ),
    "IMAGE": FunctionInfo(
        name="IMAGE",
        category="Web",
        args=("source", "[alt_text]", "[sizing]", "[height]", "[width]"),
        desc="Inserts an image from a given source URL.",
        classic=False,
    ),
    "IMAGINARY": FunctionInfo(
        name="IMAGINARY",
        category="Engineering",
        args=("inumber",),
        desc="Returns the imaginary coefficient of a complex number.",
        classic=True,
    ),
    "IMARGUMENT": FunctionInfo(
        name="IMARGUMENT",
        category="Engineering",
        args=("inumber",),
        desc="Returns the argument q, an angle expressed in radians.",
        classic=True,
    ),
    "IMCONJUGATE": FunctionInfo(
        name="IMCONJUGATE",
        category="Engineering",
        args=("inumber",),
        desc="Returns the complex conjugate of a complex number.",
        classic=True,
    ),
    "IMCOS": FunctionInfo(
        name="IMCOS",
        category="Engineering",
        args=("inumber",),
        desc="Returns the cosine of a complex number.",
        classic=True,
    ),
    "IMCOSH": FunctionInfo(
        name="IMCOSH",
        category="Engineering",
        args=("inumber",),
        desc="Returns the hyperbolic cosine of a complex number.",
        classic=False,
    ),
    "IMCOT": FunctionInfo(
        name="IMCOT",
        category="Engineering",
        args=("inumber",),
        desc="Returns the cotangent of a complex number.",
        classic=False,
    ),
    "IMCSC": FunctionInfo(
        name="IMCSC",
        category="Engineering",
        args=("inumber",),
        desc="Returns the cosecant of a complex number.",
        classic=False,
    ),
    "IMCSCH": FunctionInfo(
        name="IMCSCH",
        category="Engineering",
        args=("inumber",),
        desc="Returns the hyperbolic cosecant of a complex number.",
        classic=False,
    ),
    "IMDIV": FunctionInfo(
        name="IMDIV",
        category="Engineering",
        args=("inumber1", "inumber2"),
        desc="Returns the quotient of two complex numbers.",
        classic=True,
    ),
    "IMEXP": FunctionInfo(
        name="IMEXP",
        category="Engineering",
        args=("inumber",),
        desc="Returns the exponential of a complex number.",
        classic=True,
    ),
    "IMLN": FunctionInfo(
        name="IMLN",
        category="Engineering",
        args=("inumber",),
        desc="Returns the natural logarithm of a complex number.",
        classic=True,
    ),
    "IMLOG10": FunctionInfo(
        name="IMLOG10",
        category="Engineering",
        args=("inumber",),
        desc="Returns the base-10 logarithm of a complex number.",
        classic=True,
    ),
    "IMLOG2": FunctionInfo(
        name="IMLOG2",
        category="Engineering",
        args=("inumber",),
        desc="Returns the base-2 logarithm of a complex number.",
        classic=True,
    ),
    "IMPOWER": FunctionInfo(
        name="IMPOWER",
        category="Engineering",
        args=("inumber", "number"),
        desc="Returns a complex number raised to an integer power.",
        classic=True,
    ),
    "IMPRODUCT": FunctionInfo(
        name="IMPRODUCT",
        category="Engineering",
        args=("inumber1", "[inumber2]", "..."),
        desc="Returns the product of 1 to 255 complex numbers.",
        classic=True,
    ),
    "IMREAL": FunctionInfo(
        name="IMREAL",
        category="Engineering",
        args=("inumber",),
        desc="Returns the real coefficient of a complex number.",
        classic=True,
    ),
    "IMSEC": FunctionInfo(
        name="IMSEC",
        category="Engineering",
        args=("inumber",),
        desc="Returns the secant of a complex number.",
        classic=False,
    ),
    "IMSECH": FunctionInfo(
        name="IMSECH",
        category="Engineering",
        args=("inumber",),
        desc="Returns the hyperbolic secant of a complex number.",
        classic=False,
    ),
    "IMSIN": FunctionInfo(
        name="IMSIN",
        category="Engineering",
        args=("inumber",),
        desc="Returns the sine of a complex number.",
        classic=True,
    ),
    "IMSINH": FunctionInfo(
        name="IMSINH",
        category="Engineering",
        args=("inumber",),
        desc="Returns the hyperbolic sine of a complex number.",
        classic=False,
    ),
    "IMSQRT": FunctionInfo(
        name="IMSQRT",
        category="Engineering",
        args=("inumber",),
        desc="Returns the square root of a complex number.",
        classic=True,
    ),
    "IMSUB": FunctionInfo(
        name="IMSUB",
        category="Engineering",
        args=("inumber1", "inumber2"),
        desc="Returns the difference of two complex numbers.",
        classic=True,
    ),
    "IMSUM": FunctionInfo(
        name="IMSUM",
        category="Engineering",
        args=("inumber1", "[inumber2]", "..."),
        desc="Returns the sum of complex numbers.",
        classic=True,
    ),
    "IMTAN": FunctionInfo(
        name="IMTAN",
        category="Engineering",
        args=("inumber",),
        desc="Returns the tangent of a complex number.",
        classic=False,
    ),
    "INDEX": FunctionInfo(
        name="INDEX",
        category="Lookup & Reference",
        args=("array", "row_num", "[column_num]", "[area_num]"),
        desc=(
            "Returns a value or reference of the cell at the intersection of a "
            "particular row and column, in a given range."
        ),
        classic=True,
    ),
    "INDIRECT": FunctionInfo(
        name="INDIRECT",
        category="Lookup & Reference",
        args=("ref_text", "[a1]"),
        desc="Returns the reference specified by a text string.",
        classic=True,
    ),
    "INFO": FunctionInfo(
        name="INFO",
        category="Information",
        args=("type_text",),
        desc="Returns information about the current operating environment.",
        classic=True,
    ),
    "INT": FunctionInfo(
        name="INT",
        category="Math & Trig",
        args=("number",),
        desc="Rounds a number down to the nearest integer.",
        classic=True,
    ),
    "INTERCEPT": FunctionInfo(
        name="INTERCEPT",
        category="Statistical",
        args=("known_y's", "known_x's"),
        desc=(
            "Calculates the point at which a line will intersect the y-axis by using a "
            "best-fit regression line plotted through the known x-values and y-values."
        ),
        classic=True,
    ),
    "INTRATE": FunctionInfo(
        name="INTRATE",
        category="Financial",
        args=("settlement", "maturity", "investment", "redemption", "[basis]"),
        desc="Returns the interest rate for a fully invested security.",
        classic=True,
    ),
    "IPMT": FunctionInfo(
        name="IPMT",
        category="Financial",
        args=("rate", "per", "nper", "pv", "[fv]", "[type]"),
        desc=(
            "Returns the interest payment for a given period for an investment, based on "
            "periodic, constant payments and a constant interest rate."
        ),
        classic=True,
    ),
    "IRR": FunctionInfo(
        name="IRR",
        category="Financial",
        args=("values", "[guess]"),
        desc="Returns the internal rate of return for a series of cash flows.",
        classic=True,
    ),
    "ISBLANK": FunctionInfo(
        name="ISBLANK",
        category="Information",
        args=("value",),
        desc="Checks whether a reference is to an empty cell, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISERR": FunctionInfo(
        name="ISERR",
        category="Information",
        args=("value",),
        desc="Checks whether a value is an error other than #N/A, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISERROR": FunctionInfo(
        name="ISERROR",
        category="Information",
        args=("value",),
        desc="Checks whether a value is an error, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISEVEN": FunctionInfo(
        name="ISEVEN",
        category="Information",
        args=("number",),
        desc="Returns TRUE if the number is even.",
        classic=True,
    ),
    "ISFORMULA": FunctionInfo(
        name="ISFORMULA",
        category="Information",
        args=("reference",),
        desc=(
            "Checks whether a reference is to a cell containing a formula, and returns "
            "TRUE or FALSE."
        ),
        classic=False,
    ),
    "ISLOGICAL": FunctionInfo(
        name="ISLOGICAL",
        category="Information",
        args=("value",),
        desc=(
            "Checks whether a value is a logical value (TRUE or FALSE), and returns TRUE or FALSE."
        ),
        classic=True,
    ),
    "ISNA": FunctionInfo(
        name="ISNA",
        category="Information",
        args=("value",),
        desc="Checks whether a value is #N/A, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISNONTEXT": FunctionInfo(
        name="ISNONTEXT",
        category="Information",
        args=("value",),
        desc=(
            "Checks whether a value is not text (blank cells are not text), and returns "
            "TRUE or FALSE."
        ),
        classic=True,
    ),
    "ISNUMBER": FunctionInfo(
        name="ISNUMBER",
        category="Information",
        args=("value",),
        desc="Checks whether a value is a number, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISO.CEILING": FunctionInfo(
        name="ISO.CEILING",
        category="Math & Trig",
        args=("number", "[significance]"),
        desc=(
            "Rounds a number up to the nearest integer or to the nearest multiple of significance."
        ),
        classic=False,
    ),
    "ISODD": FunctionInfo(
        name="ISODD",
        category="Information",
        args=("number",),
        desc="Returns TRUE if the number is odd.",
        classic=True,
    ),
    "ISOMITTED": FunctionInfo(
        name="ISOMITTED",
        category="Information",
        args=("argument",),
        desc="Checks whether the value in a LAMBDA is missing and returns TRUE or FALSE.",
        classic=False,
    ),
    "ISOWEEKNUM": FunctionInfo(
        name="ISOWEEKNUM",
        category="Date & Time",
        args=("date",),
        desc="Returns the ISO week number in the year for a given date.",
        classic=False,
    ),
    "ISPMT": FunctionInfo(
        name="ISPMT",
        category="Financial",
        args=("rate", "per", "nper", "pv"),
        desc="Returns the interest paid during a specific period of an investment.",
        classic=True,
    ),
    "ISREF": FunctionInfo(
        name="ISREF",
        category="Information",
        args=("value",),
        desc="Checks whether a value is a reference, and returns TRUE or FALSE.",
        classic=True,
    ),
    "ISTEXT": FunctionInfo(
        name="ISTEXT",
        category="Information",
        args=("value",),
        desc="Checks whether a value is text, and returns TRUE or FALSE.",
        classic=True,
    ),
    "JIS": FunctionInfo(
        name="JIS",
        category="Text",
        args=("text",),
        desc="Changes half-width (single-byte) characters to full-width (double-byte) characters.",
        classic=True,
    ),
    "KURT": FunctionInfo(
        name="KURT",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the kurtosis of a data set.",
        classic=True,
    ),
    "LAMBDA": FunctionInfo(
        name="LAMBDA",
        category="Logical",
        args=("[parameter1]", "...", "calculation"),
        desc="Creates a function value, which can be called within formulas.",
        classic=False,
    ),
    "LARGE": FunctionInfo(
        name="LARGE",
        category="Statistical",
        args=("array", "k"),
        desc="Returns the k-th largest value in a data set. For example, the fifth largest number.",
        classic=True,
    ),
    "LCM": FunctionInfo(
        name="LCM",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc="Returns the least common multiple.",
        classic=True,
    ),
    "LEFT": FunctionInfo(
        name="LEFT",
        category="Text",
        args=("text", "[num_chars]"),
        desc="Returns the specified number of characters from the start of a text string.",
        classic=True,
    ),
    "LEFTB": FunctionInfo(
        name="LEFTB",
        category="Text",
        args=("text", "[num_bytes]"),
        desc="Returns the specified number of bytes from the start of a text string.",
        classic=True,
    ),
    "LEN": FunctionInfo(
        name="LEN",
        category="Text",
        args=("text",),
        desc="Returns the number of characters in a text string.",
        classic=True,
    ),
    "LENB": FunctionInfo(
        name="LENB",
        category="Text",
        args=("text",),
        desc="Returns the number of bytes used to represent the characters in a text string.",
        classic=True,
    ),
    "LET": FunctionInfo(
        name="LET",
        category="Logical",
        args=("name1", "name_value1", "...", "calculation"),
        desc=(
            "Assigns calculated values to names which allow storing intermediate "
            "calculation results."
        ),
        classic=False,
    ),
    "LINEST": FunctionInfo(
        name="LINEST",
        category="Statistical",
        args=("known_y's", "[known_x's]", "[const]", "[stats]"),
        desc=(
            "Returns statistics that describe a linear trend matching known data points, "
            "by fitting a straight line using the least squares method."
        ),
        classic=True,
    ),
    "LN": FunctionInfo(
        name="LN",
        category="Math & Trig",
        args=("number",),
        desc="Returns the natural logarithm of a number.",
        classic=True,
    ),
    "LOG": FunctionInfo(
        name="LOG",
        category="Math & Trig",
        args=("number", "[base]"),
        desc="Returns the logarithm of a number to the base you specify.",
        classic=True,
    ),
    "LOG10": FunctionInfo(
        name="LOG10",
        category="Math & Trig",
        args=("number",),
        desc="Returns the base-10 logarithm of a number.",
        classic=True,
    ),
    "LOGEST": FunctionInfo(
        name="LOGEST",
        category="Statistical",
        args=("known_y's", "[known_x's]", "[const]", "[stats]"),
        desc="Returns statistics that describe an exponential curve matching known data points.",
        classic=True,
    ),
    "LOGINV": FunctionInfo(
        name="LOGINV",
        category="Statistical",
        args=("probability", "mean", "standard_dev"),
        desc=(
            "Returns the inverse of the lognormal cumulative distribution function of x, "
            "where ln(x) is normally distributed with parameters Mean and Standard_dev."
        ),
        classic=True,
    ),
    "LOGNORM.DIST": FunctionInfo(
        name="LOGNORM.DIST",
        category="Statistical",
        args=("x", "mean", "standard_dev", "cumulative"),
        desc=(
            "Returns the lognormal distribution of x, where ln(x) is normally "
            "distributed with parameters Mean and Standard_dev."
        ),
        classic=False,
    ),
    "LOGNORM.INV": FunctionInfo(
        name="LOGNORM.INV",
        category="Statistical",
        args=("probability", "mean", "standard_dev"),
        desc="Returns the inverse of the lognormal cumulative distribution function of x.",
        classic=False,
    ),
    "LOGNORMDIST": FunctionInfo(
        name="LOGNORMDIST",
        category="Statistical",
        args=("x", "mean", "standard_dev"),
        desc=(
            "Returns the cumulative lognormal distribution of x, where ln(x) is normally "
            "distributed with parameters Mean and Standard_dev."
        ),
        classic=True,
    ),
    "LOOKUP": FunctionInfo(
        name="LOOKUP",
        category="Lookup & Reference",
        args=("lookup_value", "lookup_vector", "[result_vector]"),
        desc="Looks up a value either from a one-row or one-column range or from an array.",
        classic=True,
    ),
    "LOWER": FunctionInfo(
        name="LOWER",
        category="Text",
        args=("text",),
        desc="Converts all letters in a text string to lowercase.",
        classic=True,
    ),
    "MAKEARRAY": FunctionInfo(
        name="MAKEARRAY",
        category="Logical",
        args=("rows", "columns", "lambda"),
        desc="Returns an array of a specified row and column size, by applying a LAMBDA.",
        classic=False,
    ),
    "MAP": FunctionInfo(
        name="MAP",
        category="Logical",
        args=("array1", "...", "lambda"),
        desc=(
            "Returns an array formed by mapping each value in the array(s) to a new "
            "value by applying a LAMBDA."
        ),
        classic=False,
    ),
    "MATCH": FunctionInfo(
        name="MATCH",
        category="Lookup & Reference",
        args=("lookup_value", "lookup_array", "[match_type]"),
        desc=(
            "Returns the relative position of an item in an array that matches a "
            "specified value in a specified order."
        ),
        classic=True,
    ),
    "MAX": FunctionInfo(
        name="MAX",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the largest value in a set of values. Ignores logical values and text.",
        classic=True,
    ),
    "MAXA": FunctionInfo(
        name="MAXA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Returns the largest value in a set of values. Does not ignore logical values and text."
        ),
        classic=True,
    ),
    "MAXIFS": FunctionInfo(
        name="MAXIFS",
        category="Statistical",
        args=("max_range", "criteria_range1", "criteria1", "..."),
        desc=(
            "Returns the maximum value among cells specified by a given set of "
            "conditions or criteria."
        ),
        classic=False,
    ),
    "MDETERM": FunctionInfo(
        name="MDETERM",
        category="Math & Trig",
        args=("array",),
        desc="Returns the matrix determinant of an array.",
        classic=True,
    ),
    "MDURATION": FunctionInfo(
        name="MDURATION",
        category="Financial",
        args=("settlement", "maturity", "coupon", "yld", "frequency", "[basis]"),
        desc=(
            "Returns the Macauley modified duration for a security with an assumed par "
            "value of $100."
        ),
        classic=True,
    ),
    "MEDIAN": FunctionInfo(
        name="MEDIAN",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the median, or the number in the middle of the set of given numbers.",
        classic=True,
    ),
    "MID": FunctionInfo(
        name="MID",
        category="Text",
        args=("text", "start_num", "num_chars"),
        desc=(
            "Returns the characters from the middle of a text string, given a starting "
            "position and length."
        ),
        classic=True,
    ),
    "MIDB": FunctionInfo(
        name="MIDB",
        category="Text",
        args=("text", "start_num", "num_bytes"),
        desc=(
            "Returns bytes from the middle of a text string, given a starting position and length."
        ),
        classic=True,
    ),
    "MIN": FunctionInfo(
        name="MIN",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the smallest number in a set of values. Ignores logical values and text.",
        classic=True,
    ),
    "MINA": FunctionInfo(
        name="MINA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Returns the smallest value in a set of values. Does not ignore logical "
            "values and text."
        ),
        classic=True,
    ),
    "MINIFS": FunctionInfo(
        name="MINIFS",
        category="Statistical",
        args=("min_range", "criteria_range1", "criteria1", "..."),
        desc=(
            "Returns the minimum value among cells specified by a given set of "
            "conditions or criteria."
        ),
        classic=False,
    ),
    "MINUTE": FunctionInfo(
        name="MINUTE",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the minute, a number from 0 to 59.",
        classic=True,
    ),
    "MINVERSE": FunctionInfo(
        name="MINVERSE",
        category="Math & Trig",
        args=("array",),
        desc="Returns the inverse matrix for the matrix stored in an array.",
        classic=True,
    ),
    "MIRR": FunctionInfo(
        name="MIRR",
        category="Financial",
        args=("values", "finance_rate", "reinvest_rate"),
        desc=(
            "Returns the internal rate of return for a series of periodic cash flows, "
            "considering both cost of investment and interest on reinvestment of cash."
        ),
        classic=True,
    ),
    "MMULT": FunctionInfo(
        name="MMULT",
        category="Math & Trig",
        args=("array1", "array2"),
        desc=(
            "Returns the matrix product of two arrays, an array with the same number of "
            "rows as array1 and columns as array2."
        ),
        classic=True,
    ),
    "MOD": FunctionInfo(
        name="MOD",
        category="Math & Trig",
        args=("number", "divisor"),
        desc="Returns the remainder after a number is divided by a divisor.",
        classic=True,
    ),
    "MODE": FunctionInfo(
        name="MODE",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the most frequently occurring, or repetitive, value in an array or "
            "range of data."
        ),
        classic=True,
    ),
    "MODE.MULT": FunctionInfo(
        name="MODE.MULT",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns a vertical array of the most frequently occurring, or repetitive, "
            "values in an array or range of data."
        ),
        classic=False,
    ),
    "MODE.SNGL": FunctionInfo(
        name="MODE.SNGL",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the most frequently occurring, or repetitive, value in an array or "
            "range of data."
        ),
        classic=False,
    ),
    "MONTH": FunctionInfo(
        name="MONTH",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the month, a number from 1 (January) to 12 (December).",
        classic=True,
    ),
    "MROUND": FunctionInfo(
        name="MROUND",
        category="Math & Trig",
        args=("number", "multiple"),
        desc="Returns a number rounded to the desired multiple.",
        classic=True,
    ),
    "MULTINOMIAL": FunctionInfo(
        name="MULTINOMIAL",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc="Returns the multinomial of a set of numbers.",
        classic=True,
    ),
    "MUNIT": FunctionInfo(
        name="MUNIT",
        category="Math & Trig",
        args=("dimension",),
        desc="Returns the unit matrix for the specified dimension.",
        classic=False,
    ),
    "N": FunctionInfo(
        name="N",
        category="Information",
        args=("value",),
        desc=(
            "Converts non-number value to a number, dates to serial numbers, TRUE to 1, "
            "anything else to 0 (zero)."
        ),
        classic=True,
    ),
    "NA": FunctionInfo(
        name="NA",
        category="Information",
        args=(),
        desc="Returns the error value #N/A (value not available).",
        classic=True,
    ),
    "NEGBINOM.DIST": FunctionInfo(
        name="NEGBINOM.DIST",
        category="Statistical",
        args=("number_f", "number_s", "probability_s", "cumulative"),
        desc="Returns the negative binomial distribution.",
        classic=False,
    ),
    "NEGBINOMDIST": FunctionInfo(
        name="NEGBINOMDIST",
        category="Statistical",
        args=("number_f", "number_s", "probability_s"),
        desc=(
            "Returns the negative binomial distribution, the probability that there will "
            "be Number_f failures before the Number_s-th success."
        ),
        classic=True,
    ),
    "NETWORKDAYS": FunctionInfo(
        name="NETWORKDAYS",
        category="Date & Time",
        args=("start_date", "end_date", "[holidays]"),
        desc="Returns the number of whole workdays between two dates.",
        classic=True,
    ),
    "NETWORKDAYS.INTL": FunctionInfo(
        name="NETWORKDAYS.INTL",
        category="Date & Time",
        args=("start_date", "end_date", "[weekend]", "[holidays]"),
        desc=(
            "Returns the number of whole workdays between two dates with custom weekend parameters."
        ),
        classic=False,
    ),
    "NOMINAL": FunctionInfo(
        name="NOMINAL",
        category="Financial",
        args=("effect_rate", "npery"),
        desc="Returns the annual nominal interest rate.",
        classic=True,
    ),
    "NORM.DIST": FunctionInfo(
        name="NORM.DIST",
        category="Statistical",
        args=("x", "mean", "standard_dev", "cumulative"),
        desc="Returns the normal distribution for the specified mean and standard deviation.",
        classic=False,
    ),
    "NORM.INV": FunctionInfo(
        name="NORM.INV",
        category="Statistical",
        args=("probability", "mean", "standard_dev"),
        desc=(
            "Returns the inverse of the normal cumulative distribution for the specified "
            "mean and standard deviation."
        ),
        classic=False,
    ),
    "NORM.S.DIST": FunctionInfo(
        name="NORM.S.DIST",
        category="Statistical",
        args=("z", "cumulative"),
        desc=(
            "Returns the standard normal distribution (has a mean of zero and a standard "
            "deviation of one)."
        ),
        classic=False,
    ),
    "NORM.S.INV": FunctionInfo(
        name="NORM.S.INV",
        category="Statistical",
        args=("probability",),
        desc="Returns the inverse of the standard normal cumulative distribution.",
        classic=False,
    ),
    "NORMDIST": FunctionInfo(
        name="NORMDIST",
        category="Statistical",
        args=("x", "mean", "standard_dev", "cumulative"),
        desc=(
            "Returns the normal cumulative distribution for the specified mean and "
            "standard deviation."
        ),
        classic=True,
    ),
    "NORMINV": FunctionInfo(
        name="NORMINV",
        category="Statistical",
        args=("probability", "mean", "standard_dev"),
        desc=(
            "Returns the inverse of the normal cumulative distribution for the specified "
            "mean and standard deviation."
        ),
        classic=True,
    ),
    "NORMSDIST": FunctionInfo(
        name="NORMSDIST",
        category="Statistical",
        args=("z",),
        desc=(
            "Returns the standard normal cumulative distribution (has a mean of zero and "
            "a standard deviation of one)."
        ),
        classic=True,
    ),
    "NORMSINV": FunctionInfo(
        name="NORMSINV",
        category="Statistical",
        args=("probability",),
        desc=(
            "Returns the inverse of the standard normal cumulative distribution (has a "
            "mean of zero and a standard deviation of one)."
        ),
        classic=True,
    ),
    "NOT": FunctionInfo(
        name="NOT",
        category="Logical",
        args=("logical",),
        desc="Changes FALSE to TRUE, or TRUE to FALSE.",
        classic=True,
    ),
    "NOW": FunctionInfo(
        name="NOW",
        category="Date & Time",
        args=(),
        desc="Returns the current date and time formatted as a date and time.",
        classic=True,
    ),
    "NPER": FunctionInfo(
        name="NPER",
        category="Financial",
        args=("rate", "pmt", "pv", "[fv]", "[type]"),
        desc=(
            "Returns the number of periods for an investment based on periodic, constant "
            "payments and a constant interest rate."
        ),
        classic=True,
    ),
    "NPV": FunctionInfo(
        name="NPV",
        category="Financial",
        args=("rate", "value1", "[value2]", "..."),
        desc=(
            "Returns the net present value of an investment based on a discount rate and "
            "a series of future payments (negative values) and income (positive values)."
        ),
        classic=True,
    ),
    "NUMBERVALUE": FunctionInfo(
        name="NUMBERVALUE",
        category="Text",
        args=("text", "[decimal_separator]", "[group_separator]"),
        desc="Converts text to number in a locale-independent manner.",
        classic=False,
    ),
    "OCT2BIN": FunctionInfo(
        name="OCT2BIN",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts an octal number to binary.",
        classic=True,
    ),
    "OCT2DEC": FunctionInfo(
        name="OCT2DEC",
        category="Engineering",
        args=("number",),
        desc="Converts an octal number to decimal.",
        classic=True,
    ),
    "OCT2HEX": FunctionInfo(
        name="OCT2HEX",
        category="Engineering",
        args=("number", "[places]"),
        desc="Converts an octal number to hexadecimal.",
        classic=True,
    ),
    "ODD": FunctionInfo(
        name="ODD",
        category="Math & Trig",
        args=("number",),
        desc="Rounds a positive number up and negative number down to the nearest odd integer.",
        classic=True,
    ),
    "ODDFPRICE": FunctionInfo(
        name="ODDFPRICE",
        category="Financial",
        args=(
            "settlement",
            "maturity",
            "issue",
            "first_coupon",
            "rate",
            "yld",
            "redemption",
            "frequency",
            "[basis]",
        ),
        desc="Returns the price per $100 face value of a security with an odd first period.",
        classic=True,
    ),
    "ODDFYIELD": FunctionInfo(
        name="ODDFYIELD",
        category="Financial",
        args=(
            "settlement",
            "maturity",
            "issue",
            "first_coupon",
            "rate",
            "pr",
            "redemption",
            "frequency",
            "[basis]",
        ),
        desc="Returns the yield of a security with an odd first period.",
        classic=True,
    ),
    "ODDLPRICE": FunctionInfo(
        name="ODDLPRICE",
        category="Financial",
        args=(
            "settlement",
            "maturity",
            "last_interest",
            "rate",
            "yld",
            "redemption",
            "frequency",
            "[basis]",
        ),
        desc="Returns the price per $100 face value of a security with an odd last period.",
        classic=True,
    ),
    "ODDLYIELD": FunctionInfo(
        name="ODDLYIELD",
        category="Financial",
        args=(
            "settlement",
            "maturity",
            "last_interest",
            "rate",
            "pr",
            "redemption",
            "frequency",
            "[basis]",
        ),
        desc="Returns the yield of a security with an odd last period.",
        classic=True,
    ),
    "OFFSET": FunctionInfo(
        name="OFFSET",
        category="Lookup & Reference",
        args=("reference", "rows", "cols", "[height]", "[width]"),
        desc=(
            "Returns a reference to a range that is a given number of rows and columns "
            "from a given reference."
        ),
        classic=True,
    ),
    "OR": FunctionInfo(
        name="OR",
        category="Logical",
        args=("logical1", "[logical2]", "..."),
        desc=(
            "Checks whether any of the arguments are TRUE, and returns TRUE or FALSE. "
            "Returns FALSE only if all arguments are FALSE."
        ),
        classic=True,
    ),
    "PDURATION": FunctionInfo(
        name="PDURATION",
        category="Financial",
        args=("rate", "pv", "fv"),
        desc="Returns the number of periods required by an investment to reach a specified value.",
        classic=False,
    ),
    "PEARSON": FunctionInfo(
        name="PEARSON",
        category="Statistical",
        args=("array1", "array2"),
        desc="Returns the Pearson product moment correlation coefficient, r.",
        classic=True,
    ),
    "PERCENTILE": FunctionInfo(
        name="PERCENTILE",
        category="Statistical",
        args=("array", "k"),
        desc="Returns the k-th percentile of values in a range.",
        classic=True,
    ),
    "PERCENTILE.EXC": FunctionInfo(
        name="PERCENTILE.EXC",
        category="Statistical",
        args=("array", "k"),
        desc=(
            "Returns the k-th percentile of values in a range, where k is in the range "
            "0..1, exclusive."
        ),
        classic=False,
    ),
    "PERCENTILE.INC": FunctionInfo(
        name="PERCENTILE.INC",
        category="Statistical",
        args=("array", "k"),
        desc=(
            "Returns the k-th percentile of values in a range, where k is in the range "
            "0..1, inclusive."
        ),
        classic=False,
    ),
    "PERCENTRANK": FunctionInfo(
        name="PERCENTRANK",
        category="Statistical",
        args=("array", "x", "[significance]"),
        desc="Returns the rank of a value in a data set as a percentage of the data set.",
        classic=True,
    ),
    "PERCENTRANK.EXC": FunctionInfo(
        name="PERCENTRANK.EXC",
        category="Statistical",
        args=("array", "x", "[significance]"),
        desc=(
            "Returns the rank of a value in a data set as a percentage of the data set "
            "(0..1, exclusive)."
        ),
        classic=False,
    ),
    "PERCENTRANK.INC": FunctionInfo(
        name="PERCENTRANK.INC",
        category="Statistical",
        args=("array", "x", "[significance]"),
        desc=(
            "Returns the rank of a value in a data set as a percentage of the data set "
            "(0..1, inclusive)."
        ),
        classic=False,
    ),
    "PERMUT": FunctionInfo(
        name="PERMUT",
        category="Statistical",
        args=("number", "number_chosen"),
        desc=(
            "Returns the number of permutations for a given number of objects that can "
            "be selected from the total objects."
        ),
        classic=True,
    ),
    "PERMUTATIONA": FunctionInfo(
        name="PERMUTATIONA",
        category="Statistical",
        args=("number", "number_chosen"),
        desc=(
            "Returns the number of permutations for a given number of objects (with "
            "repetitions) that can be selected from the total objects."
        ),
        classic=False,
    ),
    "PHI": FunctionInfo(
        name="PHI",
        category="Statistical",
        args=("x",),
        desc="Returns the value of the density function for a standard normal distribution.",
        classic=False,
    ),
    "PHONETIC": FunctionInfo(
        name="PHONETIC",
        category="Text",
        args=("reference",),
        desc="Extracts the phonetic (furigana) characters from a text string.",
        classic=True,
    ),
    "PI": FunctionInfo(
        name="PI",
        category="Math & Trig",
        args=(),
        desc="Returns the value of Pi, 3.14159265358979, accurate to 15 digits.",
        classic=True,
    ),
    "PMT": FunctionInfo(
        name="PMT",
        category="Financial",
        args=("rate", "nper", "pv", "[fv]", "[type]"),
        desc=(
            "Calculates the payment for a loan based on constant payments and a constant "
            "interest rate."
        ),
        classic=True,
    ),
    "POISSON": FunctionInfo(
        name="POISSON",
        category="Statistical",
        args=("x", "mean", "cumulative"),
        desc="Returns the Poisson distribution.",
        classic=True,
    ),
    "POISSON.DIST": FunctionInfo(
        name="POISSON.DIST",
        category="Statistical",
        args=("x", "mean", "cumulative"),
        desc="Returns the Poisson distribution.",
        classic=False,
    ),
    "POWER": FunctionInfo(
        name="POWER",
        category="Math & Trig",
        args=("number", "power"),
        desc="Returns the result of a number raised to a power.",
        classic=True,
    ),
    "PPMT": FunctionInfo(
        name="PPMT",
        category="Financial",
        args=("rate", "per", "nper", "pv", "[fv]", "[type]"),
        desc=(
            "Returns the payment on the principal for a given investment based on "
            "periodic, constant payments and a constant interest rate."
        ),
        classic=True,
    ),
    "PRICE": FunctionInfo(
        name="PRICE",
        category="Financial",
        args=("settlement", "maturity", "rate", "yld", "redemption", "frequency", "[basis]"),
        desc="Returns the price per $100 face value of a security that pays periodic interest.",
        classic=True,
    ),
    "PRICEDISC": FunctionInfo(
        name="PRICEDISC",
        category="Financial",
        args=("settlement", "maturity", "discount", "redemption", "[basis]"),
        desc="Returns the price per $100 face value of a discounted security.",
        classic=True,
    ),
    "PRICEMAT": FunctionInfo(
        name="PRICEMAT",
        category="Financial",
        args=("settlement", "maturity", "issue", "rate", "yld", "[basis]"),
        desc="Returns the price per $100 face value of a security that pays interest at maturity.",
        classic=True,
    ),
    "PROB": FunctionInfo(
        name="PROB",
        category="Statistical",
        args=("x_range", "prob_range", "lower_limit", "[upper_limit]"),
        desc=(
            "Returns the probability that values in a range are between two limits or "
            "equal to a lower limit."
        ),
        classic=True,
    ),
    "PRODUCT": FunctionInfo(
        name="PRODUCT",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc="Multiplies all the numbers given as arguments.",
        classic=True,
    ),
    "PROPER": FunctionInfo(
        name="PROPER",
        category="Text",
        args=("text",),
        desc=(
            "Converts a text string to proper case; the first letter in each word in "
            "uppercase, and all other letters to lowercase."
        ),
        classic=True,
    ),
    "PV": FunctionInfo(
        name="PV",
        category="Financial",
        args=("rate", "nper", "pmt", "[fv]", "[type]"),
        desc=(
            "Returns the present value of an investment: the total amount that a series "
            "of future payments is worth now."
        ),
        classic=True,
    ),
    "PY": FunctionInfo(
        name="PY",
        category="Engineering",
        args=("python_code", "[return_type]"),
        desc="Executes Python formula code within Excel.",
        classic=False,
    ),
    "QUARTILE": FunctionInfo(
        name="QUARTILE",
        category="Statistical",
        args=("array", "quart"),
        desc="Returns the quartile of a data set.",
        classic=True,
    ),
    "QUARTILE.EXC": FunctionInfo(
        name="QUARTILE.EXC",
        category="Statistical",
        args=("array", "quart"),
        desc="Returns the quartile of a data set, based on percentile values from 0..1, exclusive.",
        classic=False,
    ),
    "QUARTILE.INC": FunctionInfo(
        name="QUARTILE.INC",
        category="Statistical",
        args=("array", "quart"),
        desc="Returns the quartile of a data set, based on percentile values from 0..1, inclusive.",
        classic=False,
    ),
    "QUOTIENT": FunctionInfo(
        name="QUOTIENT",
        category="Math & Trig",
        args=("numerator", "denominator"),
        desc="Returns the integer portion of a division.",
        classic=True,
    ),
    "RADIANS": FunctionInfo(
        name="RADIANS",
        category="Math & Trig",
        args=("angle",),
        desc="Converts degrees to radians.",
        classic=True,
    ),
    "RAND": FunctionInfo(
        name="RAND",
        category="Math & Trig",
        args=(),
        desc=(
            "Returns a random number greater than or equal to 0 and less than 1, evenly "
            "distributed (changes on recalculation)."
        ),
        classic=True,
    ),
    "RANDARRAY": FunctionInfo(
        name="RANDARRAY",
        category="Math & Trig",
        args=("[rows]", "[columns]", "[min]", "[max]", "[integer]"),
        desc="Returns an array of random numbers.",
        classic=False,
    ),
    "RANDBETWEEN": FunctionInfo(
        name="RANDBETWEEN",
        category="Math & Trig",
        args=("bottom", "top"),
        desc="Returns a random number between the numbers you specify.",
        classic=True,
    ),
    "RANK": FunctionInfo(
        name="RANK",
        category="Statistical",
        args=("number", "ref", "[order]"),
        desc=(
            "Returns the rank of a number in a list of numbers: its size relative to "
            "other values in the list."
        ),
        classic=True,
    ),
    "RANK.AVG": FunctionInfo(
        name="RANK.AVG",
        category="Statistical",
        args=("number", "ref", "[order]"),
        desc=(
            "Returns the rank of a number in a list of numbers; if more than one value "
            "has the same rank, the average rank is returned."
        ),
        classic=False,
    ),
    "RANK.EQ": FunctionInfo(
        name="RANK.EQ",
        category="Statistical",
        args=("number", "ref", "[order]"),
        desc=(
            "Returns the rank of a number in a list of numbers; if more than one value "
            "has the same rank, the top rank of that set of values is returned."
        ),
        classic=False,
    ),
    "RATE": FunctionInfo(
        name="RATE",
        category="Financial",
        args=("nper", "pmt", "pv", "[fv]", "[type]", "[guess]"),
        desc="Returns the interest rate per period of a loan or an investment.",
        classic=True,
    ),
    "RECEIVED": FunctionInfo(
        name="RECEIVED",
        category="Financial",
        args=("settlement", "maturity", "investment", "discount", "[basis]"),
        desc="Returns the amount received at maturity for a fully invested security.",
        classic=True,
    ),
    "REDUCE": FunctionInfo(
        name="REDUCE",
        category="Logical",
        args=("[initial_value]", "array", "lambda"),
        desc="Reduces an array to an accumulated value by applying a LAMBDA to each value.",
        classic=False,
    ),
    "REGISTER.ID": FunctionInfo(
        name="REGISTER.ID",
        category="Add-in & Automation",
        args=("module_text", "procedure", "[type_text]"),
        desc="Returns the register ID of the specified dynamic link library.",
        classic=False,
    ),
    "REPLACE": FunctionInfo(
        name="REPLACE",
        category="Text",
        args=("old_text", "start_num", "num_chars", "new_text"),
        desc="Replaces part of a text string with a different text string.",
        classic=True,
    ),
    "REPLACEB": FunctionInfo(
        name="REPLACEB",
        category="Text",
        args=("old_text", "start_num", "num_bytes", "new_text"),
        desc="Replaces part of a text string, counting bytes.",
        classic=True,
    ),
    "REPT": FunctionInfo(
        name="REPT",
        category="Text",
        args=("text", "number_times"),
        desc=(
            "Repeats text a given number of times. Use REPT to fill a cell with a number "
            "of instances of a text string."
        ),
        classic=True,
    ),
    "RIGHT": FunctionInfo(
        name="RIGHT",
        category="Text",
        args=("text", "[num_chars]"),
        desc="Returns the specified number of characters from the end of a text string.",
        classic=True,
    ),
    "RIGHTB": FunctionInfo(
        name="RIGHTB",
        category="Text",
        args=("text", "[num_bytes]"),
        desc="Returns the specified number of bytes from the end of a text string.",
        classic=True,
    ),
    "ROMAN": FunctionInfo(
        name="ROMAN",
        category="Math & Trig",
        args=("number", "[form]"),
        desc="Converts an Arabic numeral to Roman, as text.",
        classic=True,
    ),
    "ROUND": FunctionInfo(
        name="ROUND",
        category="Math & Trig",
        args=("number", "num_digits"),
        desc="Rounds a number to a specified number of digits.",
        classic=True,
    ),
    "ROUNDDOWN": FunctionInfo(
        name="ROUNDDOWN",
        category="Math & Trig",
        args=("number", "num_digits"),
        desc="Rounds a number down, toward zero.",
        classic=True,
    ),
    "ROUNDUP": FunctionInfo(
        name="ROUNDUP",
        category="Math & Trig",
        args=("number", "num_digits"),
        desc="Rounds a number up, away from zero.",
        classic=True,
    ),
    "ROW": FunctionInfo(
        name="ROW",
        category="Lookup & Reference",
        args=("[reference]",),
        desc="Returns the row number of a reference.",
        classic=True,
    ),
    "ROWS": FunctionInfo(
        name="ROWS",
        category="Lookup & Reference",
        args=("array",),
        desc="Returns the number of rows in a reference or an array.",
        classic=True,
    ),
    "RRI": FunctionInfo(
        name="RRI",
        category="Financial",
        args=("nper", "pv", "fv"),
        desc="Returns an equivalent interest rate for the growth of an investment.",
        classic=False,
    ),
    "RSQ": FunctionInfo(
        name="RSQ",
        category="Statistical",
        args=("known_y's", "known_x's"),
        desc=(
            "Returns the square of the Pearson product moment correlation coefficient "
            "through the given data points."
        ),
        classic=True,
    ),
    "RTD": FunctionInfo(
        name="RTD",
        category="Lookup & Reference",
        args=("progID", "server", "topic1", "..."),
        desc="Retrieves real-time data from a program that supports COM automation.",
        classic=True,
    ),
    "SCAN": FunctionInfo(
        name="SCAN",
        category="Logical",
        args=("[initial_value]", "array", "lambda"),
        desc=(
            "Scans an array by applying a LAMBDA to each value and returns an array that "
            "has each intermediate value."
        ),
        classic=False,
    ),
    "SEARCH": FunctionInfo(
        name="SEARCH",
        category="Text",
        args=("find_text", "within_text", "[start_num]"),
        desc=(
            "Returns the number of the character at which a specific character or text "
            "string is first found, reading left to right (not case-sensitive)."
        ),
        classic=True,
    ),
    "SEARCHB": FunctionInfo(
        name="SEARCHB",
        category="Text",
        args=("find_text", "within_text", "[start_num]"),
        desc="Finds one text value within another (counting bytes, not case-sensitive).",
        classic=True,
    ),
    "SEC": FunctionInfo(
        name="SEC",
        category="Math & Trig",
        args=("number",),
        desc="Returns the secant of an angle.",
        classic=False,
    ),
    "SECH": FunctionInfo(
        name="SECH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic secant of an angle.",
        classic=False,
    ),
    "SECOND": FunctionInfo(
        name="SECOND",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the second, a number from 0 to 59.",
        classic=True,
    ),
    "SEQUENCE": FunctionInfo(
        name="SEQUENCE",
        category="Math & Trig",
        args=("rows", "[columns]", "[start]", "[step]"),
        desc="Returns a sequence of numbers.",
        classic=False,
    ),
    "SERIESSUM": FunctionInfo(
        name="SERIESSUM",
        category="Math & Trig",
        args=("x", "n", "m", "coefficients"),
        desc="Returns the sum of a power series based on the formula.",
        classic=True,
    ),
    "SHEET": FunctionInfo(
        name="SHEET",
        category="Information",
        args=("[value]",),
        desc="Returns the sheet number of the referenced sheet.",
        classic=False,
    ),
    "SHEETS": FunctionInfo(
        name="SHEETS",
        category="Information",
        args=("[reference]",),
        desc="Returns the number of sheets in a reference.",
        classic=False,
    ),
    "SIGN": FunctionInfo(
        name="SIGN",
        category="Math & Trig",
        args=("number",),
        desc=(
            "Returns the sign of a number: 1 if the number is positive, zero if the "
            "number is zero, or -1 if the number is negative."
        ),
        classic=True,
    ),
    "SIN": FunctionInfo(
        name="SIN",
        category="Math & Trig",
        args=("number",),
        desc="Returns the sine of an angle.",
        classic=True,
    ),
    "SINGLE": FunctionInfo(
        name="SINGLE",
        category="Lookup & Reference",
        args=("value",),
        desc="Evaluates the argument using implicit intersection.",
        classic=False,
    ),
    "SINH": FunctionInfo(
        name="SINH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic sine of a number.",
        classic=True,
    ),
    "SKEW": FunctionInfo(
        name="SKEW",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the skewness of a distribution: a characterization of the degree of "
            "asymmetry of a distribution around its mean."
        ),
        classic=True,
    ),
    "SKEW.P": FunctionInfo(
        name="SKEW.P",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc="Returns the skewness of a distribution based on a population.",
        classic=False,
    ),
    "SLN": FunctionInfo(
        name="SLN",
        category="Financial",
        args=("cost", "salvage", "life"),
        desc="Returns the straight-line depreciation of an asset for one period.",
        classic=True,
    ),
    "SLOPE": FunctionInfo(
        name="SLOPE",
        category="Statistical",
        args=("known_y's", "known_x's"),
        desc="Returns the slope of the linear regression line through the given data points.",
        classic=True,
    ),
    "SMALL": FunctionInfo(
        name="SMALL",
        category="Statistical",
        args=("array", "k"),
        desc=(
            "Returns the k-th smallest value in a data set. For example, the fifth smallest number."
        ),
        classic=True,
    ),
    "SORT": FunctionInfo(
        name="SORT",
        category="Lookup & Reference",
        args=("array", "[sort_index]", "[sort_order]", "[by_col]"),
        desc="Sorts a range or array.",
        classic=False,
    ),
    "SORTBY": FunctionInfo(
        name="SORTBY",
        category="Lookup & Reference",
        args=("array", "by_array1", "[sort_order1]", "..."),
        desc="Sorts a range or array based on the values in a corresponding range or array.",
        classic=False,
    ),
    "SQL.REQUEST": FunctionInfo(
        name="SQL.REQUEST",
        category="Database",
        args=(
            "connection_string",
            "[output_ref]",
            "[driver_prompt]",
            "[query_text]",
            "[col_names_logical]",
        ),
        desc="Connects to an external data source and runs a query.",
        classic=False,
    ),
    "SQRT": FunctionInfo(
        name="SQRT",
        category="Math & Trig",
        args=("number",),
        desc="Returns the square root of a number.",
        classic=True,
    ),
    "SQRTPI": FunctionInfo(
        name="SQRTPI",
        category="Math & Trig",
        args=("number",),
        desc="Returns the square root of (number * Pi).",
        classic=True,
    ),
    "STANDARDIZE": FunctionInfo(
        name="STANDARDIZE",
        category="Statistical",
        args=("x", "mean", "standard_dev"),
        desc=(
            "Returns a normalized value from a distribution characterized by a mean and "
            "standard deviation."
        ),
        classic=True,
    ),
    "STDEV": FunctionInfo(
        name="STDEV",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Estimates standard deviation based on a sample (ignores logical values and "
            "text in the sample)."
        ),
        classic=True,
    ),
    "STDEV.P": FunctionInfo(
        name="STDEV.P",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Calculates standard deviation based on the entire population given as "
            "arguments (ignores logical values and text)."
        ),
        classic=False,
    ),
    "STDEV.S": FunctionInfo(
        name="STDEV.S",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Estimates standard deviation based on a sample (ignores logical values and "
            "text in the sample)."
        ),
        classic=False,
    ),
    "STDEVA": FunctionInfo(
        name="STDEVA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Estimates standard deviation based on a sample, including logical values "
            "and text. Text and FALSE have the value 0; TRUE has the value 1."
        ),
        classic=True,
    ),
    "STDEVP": FunctionInfo(
        name="STDEVP",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Calculates standard deviation based on the entire population given as "
            "arguments (ignores logical values and text)."
        ),
        classic=True,
    ),
    "STDEVPA": FunctionInfo(
        name="STDEVPA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Calculates standard deviation based on an entire population, including "
            "logical values and text."
        ),
        classic=True,
    ),
    "STEYX": FunctionInfo(
        name="STEYX",
        category="Statistical",
        args=("known_y's", "known_x's"),
        desc="Returns the standard error of the predicted y-value for each x in a regression.",
        classic=True,
    ),
    "STOCKHISTORY": FunctionInfo(
        name="STOCKHISTORY",
        category="Financial",
        args=("stock", "start_date", "[end_date]", "[interval]", "[headers]", "[properties]"),
        desc="Retrieves historical financial data.",
        classic=False,
    ),
    "SUBSTITUTE": FunctionInfo(
        name="SUBSTITUTE",
        category="Text",
        args=("text", "old_text", "new_text", "[instance_num]"),
        desc="Replaces existing text with new text in a text string.",
        classic=True,
    ),
    "SUBTOTAL": FunctionInfo(
        name="SUBTOTAL",
        category="Math & Trig",
        args=("function_num", "ref1", "..."),
        desc="Returns a subtotal in a list or database.",
        classic=True,
    ),
    "SUM": FunctionInfo(
        name="SUM",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc="Adds all the numbers in a range of cells.",
        classic=True,
    ),
    "SUMIF": FunctionInfo(
        name="SUMIF",
        category="Math & Trig",
        args=("range", "criteria", "[sum_range]"),
        desc="Adds the cells specified by a given condition or criteria.",
        classic=True,
    ),
    "SUMIFS": FunctionInfo(
        name="SUMIFS",
        category="Math & Trig",
        args=("sum_range", "criteria_range1", "criteria1", "..."),
        desc="Adds the cells specified by a given set of conditions or criteria.",
        classic=False,
    ),
    "SUMPRODUCT": FunctionInfo(
        name="SUMPRODUCT",
        category="Math & Trig",
        args=("array1", "[array2]", "..."),
        desc="Returns the sum of the products of corresponding ranges or arrays.",
        classic=True,
    ),
    "SUMSQ": FunctionInfo(
        name="SUMSQ",
        category="Math & Trig",
        args=("number1", "[number2]", "..."),
        desc=(
            "Returns the sum of the squares of the arguments. The arguments can be "
            "numbers, arrays, names or references to cells that contain numbers."
        ),
        classic=True,
    ),
    "SUMX2MY2": FunctionInfo(
        name="SUMX2MY2",
        category="Math & Trig",
        args=("array_x", "array_y"),
        desc="Sums the differences between the squares of two corresponding ranges or arrays.",
        classic=True,
    ),
    "SUMX2PY2": FunctionInfo(
        name="SUMX2PY2",
        category="Math & Trig",
        args=("array_x", "array_y"),
        desc=(
            "Returns the sum total of the sums of squares of numbers in two "
            "corresponding ranges or arrays."
        ),
        classic=True,
    ),
    "SUMXMY2": FunctionInfo(
        name="SUMXMY2",
        category="Math & Trig",
        args=("array_x", "array_y"),
        desc="Sums the squares of the differences in two corresponding ranges or arrays.",
        classic=True,
    ),
    "SWITCH": FunctionInfo(
        name="SWITCH",
        category="Logical",
        args=("expression", "value1", "result1", "..."),
        desc=(
            "Evaluates an expression against a list of values and returns the result "
            "corresponding to the first matching value."
        ),
        classic=False,
    ),
    "SYD": FunctionInfo(
        name="SYD",
        category="Financial",
        args=("cost", "salvage", "life", "per"),
        desc="Returns the sum-of-years' digits depreciation of an asset for a specified period.",
        classic=True,
    ),
    "T": FunctionInfo(
        name="T",
        category="Text",
        args=("value",),
        desc=(
            "Checks whether a value is text, and returns the text if it is, or returns "
            "double quotes (empty text) if it is not."
        ),
        classic=True,
    ),
    "T.DIST": FunctionInfo(
        name="T.DIST",
        category="Statistical",
        args=("x", "deg_freedom", "cumulative"),
        desc="Returns the left-tailed Student's t-distribution.",
        classic=False,
    ),
    "T.DIST.2T": FunctionInfo(
        name="T.DIST.2T",
        category="Statistical",
        args=("x", "deg_freedom"),
        desc="Returns the two-tailed Student's t-distribution.",
        classic=False,
    ),
    "T.DIST.RT": FunctionInfo(
        name="T.DIST.RT",
        category="Statistical",
        args=("x", "deg_freedom"),
        desc="Returns the right-tailed Student's t-distribution.",
        classic=False,
    ),
    "T.INV": FunctionInfo(
        name="T.INV",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the left-tailed inverse of the Student's t-distribution.",
        classic=False,
    ),
    "T.INV.2T": FunctionInfo(
        name="T.INV.2T",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the two-tailed inverse of the Student's t-distribution.",
        classic=False,
    ),
    "T.TEST": FunctionInfo(
        name="T.TEST",
        category="Statistical",
        args=("array1", "array2", "tails", "type"),
        desc="Returns the probability associated with a Student's t-Test.",
        classic=False,
    ),
    "TAKE": FunctionInfo(
        name="TAKE",
        category="Lookup & Reference",
        args=("array", "rows", "[columns]"),
        desc="Returns rows or columns from the start or end of an array.",
        classic=False,
    ),
    "TAN": FunctionInfo(
        name="TAN",
        category="Math & Trig",
        args=("number",),
        desc="Returns the tangent of an angle.",
        classic=True,
    ),
    "TANH": FunctionInfo(
        name="TANH",
        category="Math & Trig",
        args=("number",),
        desc="Returns the hyperbolic tangent of a number.",
        classic=True,
    ),
    "TBILLEQ": FunctionInfo(
        name="TBILLEQ",
        category="Financial",
        args=("settlement", "maturity", "discount"),
        desc="Returns the bond-equivalent yield for a Treasury bill.",
        classic=True,
    ),
    "TBILLPRICE": FunctionInfo(
        name="TBILLPRICE",
        category="Financial",
        args=("settlement", "maturity", "discount"),
        desc="Returns the price per $100 face value for a Treasury bill.",
        classic=True,
    ),
    "TBILLYIELD": FunctionInfo(
        name="TBILLYIELD",
        category="Financial",
        args=("settlement", "maturity", "pr"),
        desc="Returns the yield for a Treasury bill.",
        classic=True,
    ),
    "TDIST": FunctionInfo(
        name="TDIST",
        category="Statistical",
        args=("x", "deg_freedom", "tails"),
        desc="Returns the Student's t-distribution.",
        classic=True,
    ),
    "TEXT": FunctionInfo(
        name="TEXT",
        category="Text",
        args=("value", "format_text"),
        desc="Converts a value to text in a specific number format.",
        classic=True,
    ),
    "TEXTAFTER": FunctionInfo(
        name="TEXTAFTER",
        category="Text",
        args=(
            "text",
            "delimiter",
            "[instance_num]",
            "[match_mode]",
            "[match_end]",
            "[if_not_found]",
        ),
        desc="Returns text that occurs after a given character or string.",
        classic=False,
    ),
    "TEXTBEFORE": FunctionInfo(
        name="TEXTBEFORE",
        category="Text",
        args=(
            "text",
            "delimiter",
            "[instance_num]",
            "[match_mode]",
            "[match_end]",
            "[if_not_found]",
        ),
        desc="Returns text that occurs before a given character or string.",
        classic=False,
    ),
    "TEXTJOIN": FunctionInfo(
        name="TEXTJOIN",
        category="Text",
        args=("delimiter", "ignore_empty", "text1", "..."),
        desc="Concatenates a list or range of text strings using a delimiter.",
        classic=False,
    ),
    "TEXTSPLIT": FunctionInfo(
        name="TEXTSPLIT",
        category="Text",
        args=(
            "text",
            "col_delimiter",
            "[row_delimiter]",
            "[ignore_empty]",
            "[match_mode]",
            "[pad_with]",
        ),
        desc="Splits text into rows or columns using delimiters.",
        classic=False,
    ),
    "TIME": FunctionInfo(
        name="TIME",
        category="Date & Time",
        args=("hour", "minute", "second"),
        desc=(
            "Converts hours, minutes and seconds given as numbers to a Ledger serial "
            "number, formatted with a time format."
        ),
        classic=True,
    ),
    "TIMEVALUE": FunctionInfo(
        name="TIMEVALUE",
        category="Date & Time",
        args=("time_text",),
        desc=(
            "Converts a text time to a Ledger serial number for a time, a number from 0 "
            "(12:00:00 AM) to 0.999988426 (11:59:59 PM)."
        ),
        classic=True,
    ),
    "TINV": FunctionInfo(
        name="TINV",
        category="Statistical",
        args=("probability", "deg_freedom"),
        desc="Returns the two-tailed inverse of the Student's t-distribution.",
        classic=True,
    ),
    "TOCOL": FunctionInfo(
        name="TOCOL",
        category="Lookup & Reference",
        args=("array", "[ignore]", "[scan_by_column]"),
        desc="Returns the array in a single column.",
        classic=False,
    ),
    "TODAY": FunctionInfo(
        name="TODAY",
        category="Date & Time",
        args=(),
        desc="Returns the current date formatted as a date.",
        classic=True,
    ),
    "TOROW": FunctionInfo(
        name="TOROW",
        category="Lookup & Reference",
        args=("array", "[ignore]", "[scan_by_column]"),
        desc="Returns the array in a single row.",
        classic=False,
    ),
    "TRANSLATE": FunctionInfo(
        name="TRANSLATE",
        category="Web",
        args=("text", "[source_language]", "[target_language]"),
        desc="Translates text between languages.",
        classic=False,
    ),
    "TRANSPOSE": FunctionInfo(
        name="TRANSPOSE",
        category="Lookup & Reference",
        args=("array",),
        desc="Converts a vertical range of cells to a horizontal range, or vice versa.",
        classic=True,
    ),
    "TREND": FunctionInfo(
        name="TREND",
        category="Statistical",
        args=("known_y's", "[known_x's]", "[new_x's]", "[const]"),
        desc=(
            "Returns numbers in a linear trend matching known data points, using the "
            "least squares method."
        ),
        classic=True,
    ),
    "TRIM": FunctionInfo(
        name="TRIM",
        category="Text",
        args=("text",),
        desc="Removes all spaces from a text string except for single spaces between words.",
        classic=True,
    ),
    "TRIMMEAN": FunctionInfo(
        name="TRIMMEAN",
        category="Statistical",
        args=("array", "percent"),
        desc="Returns the mean of the interior portion of a set of data values.",
        classic=True,
    ),
    "TRUE": FunctionInfo(
        name="TRUE",
        category="Logical",
        args=(),
        desc="Returns the logical value TRUE.",
        classic=True,
    ),
    "TRUNC": FunctionInfo(
        name="TRUNC",
        category="Math & Trig",
        args=("number", "[num_digits]"),
        desc=(
            "Truncates a number to an integer by removing the decimal, or fractional, "
            "part of the number."
        ),
        classic=True,
    ),
    "TTEST": FunctionInfo(
        name="TTEST",
        category="Statistical",
        args=("array1", "array2", "tails", "type"),
        desc="Returns the probability associated with a Student's t-Test.",
        classic=True,
    ),
    "TYPE": FunctionInfo(
        name="TYPE",
        category="Information",
        args=("value",),
        desc=(
            "Returns an integer representing the data type of a value: number = 1; text "
            "= 2; logical value = 4; error value = 16; array = 64."
        ),
        classic=True,
    ),
    "UNICHAR": FunctionInfo(
        name="UNICHAR",
        category="Text",
        args=("number",),
        desc="Returns the Unicode character referenced by the given numeric value.",
        classic=False,
    ),
    "UNICODE": FunctionInfo(
        name="UNICODE",
        category="Text",
        args=("text",),
        desc="Returns the number (code point) corresponding to the first character of the text.",
        classic=False,
    ),
    "UNIQUE": FunctionInfo(
        name="UNIQUE",
        category="Lookup & Reference",
        args=("array", "[by_col]", "[exactly_once]"),
        desc="Returns the unique values from a range or array.",
        classic=False,
    ),
    "UPPER": FunctionInfo(
        name="UPPER",
        category="Text",
        args=("text",),
        desc="Converts a text string to all uppercase letters.",
        classic=True,
    ),
    "VALUE": FunctionInfo(
        name="VALUE",
        category="Text",
        args=("text",),
        desc="Converts a text string that represents a number to a number.",
        classic=True,
    ),
    "VALUETOTEXT": FunctionInfo(
        name="VALUETOTEXT",
        category="Text",
        args=("value", "[format]"),
        desc="Returns a text representation of a value.",
        classic=False,
    ),
    "VAR": FunctionInfo(
        name="VAR",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Estimates variance based on a sample (ignores logical values and text in the sample)."
        ),
        classic=True,
    ),
    "VAR.P": FunctionInfo(
        name="VAR.P",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Calculates variance based on the entire population (ignores logical values "
            "and text in the population)."
        ),
        classic=False,
    ),
    "VAR.S": FunctionInfo(
        name="VAR.S",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Estimates variance based on a sample (ignores logical values and text in the sample)."
        ),
        classic=False,
    ),
    "VARA": FunctionInfo(
        name="VARA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Estimates variance based on a sample, including logical values and text. "
            "Text and FALSE have the value 0; TRUE has the value 1."
        ),
        classic=True,
    ),
    "VARP": FunctionInfo(
        name="VARP",
        category="Statistical",
        args=("number1", "[number2]", "..."),
        desc=(
            "Calculates variance based on the entire population (ignores logical values "
            "and text in the population)."
        ),
        classic=True,
    ),
    "VARPA": FunctionInfo(
        name="VARPA",
        category="Statistical",
        args=("value1", "[value2]", "..."),
        desc=(
            "Calculates variance based on the entire population, including logical values and text."
        ),
        classic=True,
    ),
    "VDB": FunctionInfo(
        name="VDB",
        category="Financial",
        args=("cost", "salvage", "life", "start_period", "end_period", "[factor]", "[no_switch]"),
        desc=(
            "Returns the depreciation of an asset for any period you specify, including "
            "partial periods, using the double-declining balance method or some other "
            "method you specify."
        ),
        classic=True,
    ),
    "VLOOKUP": FunctionInfo(
        name="VLOOKUP",
        category="Lookup & Reference",
        args=("lookup_value", "table_array", "col_index_num", "[range_lookup]"),
        desc=(
            "Looks for a value in the leftmost column of a table, and then returns a "
            "value in the same row from a column you specify."
        ),
        classic=True,
    ),
    "VSTACK": FunctionInfo(
        name="VSTACK",
        category="Lookup & Reference",
        args=("array1", "[array2]", "..."),
        desc="Appends arrays vertically and in sequence.",
        classic=False,
    ),
    "WEBSERVICE": FunctionInfo(
        name="WEBSERVICE",
        category="Web",
        args=("url",),
        desc="Returns data from a web service.",
        classic=False,
    ),
    "WEEKDAY": FunctionInfo(
        name="WEEKDAY",
        category="Date & Time",
        args=("serial_number", "[return_type]"),
        desc="Returns a number from 1 to 7 identifying the day of the week of a date.",
        classic=True,
    ),
    "WEEKNUM": FunctionInfo(
        name="WEEKNUM",
        category="Date & Time",
        args=("serial_number", "[return_type]"),
        desc="Returns the week number in the year.",
        classic=True,
    ),
    "WEIBULL": FunctionInfo(
        name="WEIBULL",
        category="Statistical",
        args=("x", "alpha", "beta", "cumulative"),
        desc="Returns the Weibull distribution.",
        classic=True,
    ),
    "WEIBULL.DIST": FunctionInfo(
        name="WEIBULL.DIST",
        category="Statistical",
        args=("x", "alpha", "beta", "cumulative"),
        desc="Returns the Weibull distribution.",
        classic=False,
    ),
    "WORKDAY": FunctionInfo(
        name="WORKDAY",
        category="Date & Time",
        args=("start_date", "days", "[holidays]"),
        desc=(
            "Returns the serial number of the date before or after a specified number of workdays."
        ),
        classic=True,
    ),
    "WORKDAY.INTL": FunctionInfo(
        name="WORKDAY.INTL",
        category="Date & Time",
        args=("start_date", "days", "[weekend]", "[holidays]"),
        desc=(
            "Returns the serial number of the date before or after a specified number of "
            "workdays with custom weekend parameters."
        ),
        classic=False,
    ),
    "WRAPCOLS": FunctionInfo(
        name="WRAPCOLS",
        category="Lookup & Reference",
        args=("vector", "wrap_count", "[pad_with]"),
        desc="Wraps a row or column of values by columns after a specified number of elements.",
        classic=False,
    ),
    "WRAPROWS": FunctionInfo(
        name="WRAPROWS",
        category="Lookup & Reference",
        args=("vector", "wrap_count", "[pad_with]"),
        desc="Wraps a row or column of values by rows after a specified number of elements.",
        classic=False,
    ),
    "XIRR": FunctionInfo(
        name="XIRR",
        category="Financial",
        args=("values", "dates", "[guess]"),
        desc=(
            "Returns the internal rate of return for a schedule of cash flows that is "
            "not necessarily periodic."
        ),
        classic=True,
    ),
    "XLOOKUP": FunctionInfo(
        name="XLOOKUP",
        category="Lookup & Reference",
        args=(
            "lookup_value",
            "lookup_array",
            "return_array",
            "[if_not_found]",
            "[match_mode]",
            "[search_mode]",
        ),
        desc=(
            "Searches a range or an array for a match and returns the corresponding item "
            "from a second range or array."
        ),
        classic=False,
    ),
    "XMATCH": FunctionInfo(
        name="XMATCH",
        category="Lookup & Reference",
        args=("lookup_value", "lookup_array", "[match_mode]", "[search_mode]"),
        desc="Returns the relative position of an item in an array.",
        classic=False,
    ),
    "XNPV": FunctionInfo(
        name="XNPV",
        category="Financial",
        args=("rate", "values", "dates"),
        desc=(
            "Returns the net present value for a schedule of cash flows that is not "
            "necessarily periodic."
        ),
        classic=True,
    ),
    "XOR": FunctionInfo(
        name="XOR",
        category="Logical",
        args=("logical1", "[logical2]", "..."),
        desc="Returns a logical 'Exclusive Or' of all arguments.",
        classic=False,
    ),
    "YEAR": FunctionInfo(
        name="YEAR",
        category="Date & Time",
        args=("serial_number",),
        desc="Returns the year of a date, an integer in the range 1900 - 9999.",
        classic=True,
    ),
    "YEARFRAC": FunctionInfo(
        name="YEARFRAC",
        category="Date & Time",
        args=("start_date", "end_date", "[basis]"),
        desc=(
            "Returns the year fraction representing the number of whole days between "
            "start_date and end_date."
        ),
        classic=True,
    ),
    "YIELD": FunctionInfo(
        name="YIELD",
        category="Financial",
        args=("settlement", "maturity", "rate", "pr", "redemption", "frequency", "[basis]"),
        desc="Returns the yield on a security that pays periodic interest.",
        classic=True,
    ),
    "YIELDDISC": FunctionInfo(
        name="YIELDDISC",
        category="Financial",
        args=("settlement", "maturity", "pr", "redemption", "[basis]"),
        desc="Returns the annual yield for a discounted security, for example a Treasury bill.",
        classic=True,
    ),
    "YIELDMAT": FunctionInfo(
        name="YIELDMAT",
        category="Financial",
        args=("settlement", "maturity", "issue", "rate", "pr", "[basis]"),
        desc="Returns the annual yield of a security that pays interest at maturity.",
        classic=True,
    ),
    "Z.TEST": FunctionInfo(
        name="Z.TEST",
        category="Statistical",
        args=("array", "x", "[sigma]"),
        desc="Returns the one-tailed P-value of a z-test.",
        classic=False,
    ),
    "ZTEST": FunctionInfo(
        name="ZTEST",
        category="Statistical",
        args=("array", "x", "[sigma]"),
        desc="Returns the one-tailed P-value of a z-test.",
        classic=True,
    ),
}


def get_function_info(name: str) -> FunctionInfo | None:
    """Retrieve metadata for a worksheet function by name."""
    return ALL_FUNCTIONS_CATALOG.get(name.upper())
