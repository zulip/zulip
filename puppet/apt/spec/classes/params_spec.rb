require 'spec_helper'
describe 'apt::params', :type => :class do
  let (:title) { 'my_package' }

  it { should contain_apt__params }

  # There are 4 resources in this class currently
  # there should not be any more resources because it is a params class
  # The resources are class[apt::params], class[main], class[settings], stage[main]
  it "Should not contain any resources" do
    subject.resources.size.should == 4
  end
end
