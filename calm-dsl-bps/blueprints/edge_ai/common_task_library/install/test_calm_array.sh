if [ '@@{calm_array_index}@@' != '0' ];
then exit 0
fi

echo "StrictHostKeyChecking=no" >| ~/.ssh/config
ssh-keygen -t rsa -b 4096 -f ~/.ssh/edge_rsa -q -N ""

master_node='@@{address}@@'

for i in $(echo '@@{calm_array_address}@@' | tr ',' '\n')
do
if [ $i != "$master_node" ];
then
ssh-copy-id -i /home/ubuntu/.ssh/edge_rsa ubuntu@$i
fi
done