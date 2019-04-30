pstop
pclean
prestart
pip uninstall -y shelf-reader

echo "is shelf reader installed?"
pip freeze | grep shelf-reader
