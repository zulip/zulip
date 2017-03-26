require 'puppet'
require 'rspec-puppet'

describe "anchorrefresh" do
  let(:node) { 'testhost.example.com' }
  let :pre_condition do
    <<-ANCHORCLASS
class anchored {
  anchor { 'anchored::begin': }
  ~> anchor { 'anchored::end': }
}

class anchorrefresh {
  notify { 'first': }
  ~> class { 'anchored': }
  ~> anchor { 'final': }
}
    ANCHORCLASS
  end

  def apply_catalog_and_return_exec_rsrc
    catalog = subject.to_ral
    transaction = catalog.apply
    transaction.resource_status("Anchor[final]")
  end

  it 'propagates events through the anchored class' do
    resource = apply_catalog_and_return_exec_rsrc

    expect(resource.restarted).to eq(true)
  end
end
